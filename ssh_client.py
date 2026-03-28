"""
ssh_client.py — SSH connection pool built on Paramiko.
Supports key-based auth (RSA, Ed25519, ECDSA) with optional passphrase.
"""

from __future__ import annotations

import os
import socket
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import paramiko


@dataclass
class SSHConfig:
    host: str
    username: str
    port: int = 22
    # Key-based auth (recommended)
    private_key_path: Optional[str] = None
    passphrase: Optional[str] = None
    # Password auth (fallback)
    password: Optional[str] = None
    # Timeouts
    connect_timeout: int = 10
    command_timeout: int = 30

    def key(self) -> str:
        return f"{self.username}@{self.host}:{self.port}"


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


# ── Connection pool ───────────────────────────────────────────────────────────

_pool: dict[str, paramiko.SSHClient] = {}
_lock = threading.Lock()

KEEPALIVE_SECONDS = 30

DEFAULT_KEY_PATHS = [
    "~/.ssh/id_ed25519",
    "~/.ssh/id_rsa",
    "~/.ssh/id_ecdsa",
]


def _load_private_key(path: str, passphrase: Optional[str]) -> paramiko.PKey:
    """Try all Paramiko key types for the given file."""
    resolved = str(Path(path).expanduser())
    for cls in (
        paramiko.Ed25519Key,
        paramiko.RSAKey,
        paramiko.ECDSAKey,
    ):
        try:
            kwargs: dict = {"filename": resolved}
            if passphrase:
                kwargs["password"] = passphrase
            return cls(**kwargs)  # type: ignore[arg-type]
        except paramiko.SSHException:
            continue
        except Exception:
            continue
    raise ValueError(f"Cannot load private key from {resolved}. "
                     "Check the path and passphrase.")


def _connect(cfg: SSHConfig) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict = {
        "hostname": cfg.host,
        "port": cfg.port,
        "username": cfg.username,
        "timeout": cfg.connect_timeout,
    }

    if cfg.private_key_path:
        connect_kwargs["pkey"] = _load_private_key(cfg.private_key_path, cfg.passphrase)
    elif cfg.password:
        connect_kwargs["password"] = cfg.password
    else:
        # Auto-detect default keys
        for kp in DEFAULT_KEY_PATHS:
            expanded = str(Path(kp).expanduser())
            if Path(expanded).exists():
                try:
                    connect_kwargs["pkey"] = _load_private_key(expanded, cfg.passphrase)
                    break
                except Exception:
                    continue

    client.connect(**connect_kwargs)
    transport = client.get_transport()
    if transport:
        transport.set_keepalive(KEEPALIVE_SECONDS)
    return client


def _is_alive(client: paramiko.SSHClient) -> bool:
    try:
        transport = client.get_transport()
        if not transport or not transport.is_active():
            return False
        chan = transport.open_session(timeout=2.0)
        try:
            return chan is not None
        finally:
            if chan is not None:
                chan.close()
    except Exception:
        return False


def _discard_client(pool_key: str, expected: paramiko.SSHClient | None = None) -> None:
    client_to_close: paramiko.SSHClient | None = None
    with _lock:
        current = _pool.get(pool_key)
        if expected is not None and current is not expected:
            return
        client_to_close = _pool.pop(pool_key, None)
    if client_to_close:
        try:
            client_to_close.close()
        except Exception:
            pass


def get_client(cfg: SSHConfig) -> paramiko.SSHClient:
    pool_key = cfg.key()
    with _lock:
        existing = _pool.get(pool_key)

    if existing and _is_alive(existing):
        return existing
    if existing:
        _discard_client(pool_key, expected=existing)

    client = _connect(cfg)
    with _lock:
        _pool[pool_key] = client
    return client


def close_client(cfg: SSHConfig) -> None:
    _discard_client(cfg.key())


def close_all() -> None:
    with _lock:
        for c in _pool.values():
            try:
                c.close()
            except Exception:
                pass
        _pool.clear()


# ── Operations ────────────────────────────────────────────────────────────────

import time


_RETRY_ERRNOS = {
    32,   # EPIPE
    54,   # ECONNRESET (macOS)
    60,   # ETIMEDOUT (macOS)
    104,  # ECONNRESET (Linux)
    110,  # ETIMEDOUT (Linux)
    111,  # ECONNREFUSED (Linux)
}


def _is_retryable_ssh_error(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (
            paramiko.SSHException,
            EOFError,
            socket.timeout,
            TimeoutError,
            ConnectionResetError,
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionRefusedError,
        ),
    ):
        return True

    if isinstance(exc, OSError):
        errno = getattr(exc, "errno", None)
        if errno in _RETRY_ERRNOS:
            return True
        msg = str(exc).lower()
        if "connection reset by peer" in msg or "broken pipe" in msg or "eof" in msg:
            return True

    return False


def execute(cfg: SSHConfig, command: str) -> CommandResult:
    last_exc: BaseException | None = None
    for attempt in (1, 2):
        client = get_client(cfg)
        t0 = time.monotonic()
        try:
            _, stdout_f, stderr_f = client.exec_command(
                command, timeout=cfg.command_timeout
            )
            exit_code = stdout_f.channel.recv_exit_status()
            stdout = stdout_f.read().decode("utf-8", errors="replace").strip()
            stderr = stderr_f.read().decode("utf-8", errors="replace").strip()
            duration = int((time.monotonic() - t0) * 1000)
            return CommandResult(
                stdout=stdout, stderr=stderr, exit_code=exit_code, duration_ms=duration
            )
        except Exception as exc:
            last_exc = exc
            if attempt == 1 and _is_retryable_ssh_error(exc):
                _discard_client(cfg.key(), expected=client)
                continue
            raise
    assert last_exc is not None
    raise last_exc


def _with_sftp_retry(cfg: SSHConfig, op):
    last_exc: BaseException | None = None
    for attempt in (1, 2):
        client = get_client(cfg)
        sftp = None
        try:
            sftp = client.open_sftp()
            return op(sftp)
        except Exception as exc:
            last_exc = exc
            if attempt == 1 and _is_retryable_ssh_error(exc):
                _discard_client(cfg.key(), expected=client)
                continue
            raise
        finally:
            if sftp is not None:
                try:
                    sftp.close()
                except Exception:
                    pass
    assert last_exc is not None
    raise last_exc


def read_file(cfg: SSHConfig, path: str) -> str:
    def _op(sftp) -> str:
        with sftp.open(path, "r") as f:
            return f.read().decode("utf-8", errors="replace")

    return _with_sftp_retry(cfg, _op)


def write_file(cfg: SSHConfig, path: str, content: str) -> None:
    data = content.encode("utf-8")

    def _op(sftp) -> None:
        with sftp.open(path, "w") as f:
            f.write(data)

    _with_sftp_retry(cfg, _op)


def list_directory(cfg: SSHConfig, path: str) -> list[dict]:
    def _op(sftp) -> list[dict]:
        entries = []
        for attr in sftp.listdir_attr(path):
            is_dir = bool(attr.st_mode and (attr.st_mode & 0o40000))
            entries.append({
                "name": attr.filename,
                "size": attr.st_size or 0,
                "is_dir": is_dir,
                "modified": str(attr.st_mtime),
                "permissions": oct(attr.st_mode or 0)[-4:],
            })
        entries.sort(key=lambda e: (not e["is_dir"], e["name"]))
        return entries

    return _with_sftp_retry(cfg, _op)


def edit_file(
    cfg: SSHConfig,
    path: str,
    operation: str,
    old_text: str | None = None,
    new_text: str | None = None,
    line_number: int | None = None,
    line_numbers: list[int] | None = None,
) -> dict:
    """
    Edit a file on the remote server.
    
    Operations:
    - replace: Replace all occurrences of old_text with new_text
    - insert_after: Insert new_text after line_number
    - insert_before: Insert new_text before line_number
    - delete_lines: Delete lines at specified line_numbers
    """
    content = read_file(cfg, path)
    lines = content.splitlines(keepends=True)
    result_lines = []
    changes_made = 0
    
    if operation == "replace":
        if old_text is None or new_text is None:
            raise ValueError("replace operation requires old_text and new_text")
        new_content = content.replace(old_text, new_text)
        changes_made = content.count(old_text)
        write_file(cfg, path, new_content)
        
    elif operation == "insert_after":
        if line_number is None or new_text is None:
            raise ValueError("insert_after requires line_number and new_text")
        if line_number < 0 or line_number > len(lines):
            raise ValueError(f"line_number {line_number} out of range (0-{len(lines)})")
        for i, line in enumerate(lines):
            result_lines.append(line)
            if i == line_number - 1:
                result_lines.append(new_text + "\n" if not new_text.endswith("\n") else new_text)
                changes_made = 1
        write_file(cfg, path, "".join(result_lines))
        
    elif operation == "insert_before":
        if line_number is None or new_text is None:
            raise ValueError("insert_before requires line_number and new_text")
        if line_number < 1 or line_number > len(lines) + 1:
            raise ValueError(f"line_number {line_number} out of range (1-{len(lines) + 1})")
        for i, line in enumerate(lines, 1):
            if i == line_number:
                result_lines.append(new_text + "\n" if not new_text.endswith("\n") else new_text)
                changes_made = 1
            result_lines.append(line)
        write_file(cfg, path, "".join(result_lines))
        
    elif operation == "delete_lines":
        if not line_numbers:
            raise ValueError("delete_lines requires line_numbers list")
        line_set = set(line_numbers)
        for i, line in enumerate(lines, 1):
            if i not in line_set:
                result_lines.append(line)
            else:
                changes_made += 1
        write_file(cfg, path, "".join(result_lines))
        
    else:
        raise ValueError(f"Unknown operation: {operation}")
    
    return {
        "path": path,
        "operation": operation,
        "changes_made": changes_made,
    }
