"""
tools.py — MCP tool definitions and dispatch, shared by stdio and HTTP servers.
Minimal server-admin focused toolset: structured primitives first, shell fallback second.
"""

from __future__ import annotations

import json
import os
import shlex
from typing import Any

from ssh_client import SSHConfig, CommandResult
import ssh_client as ssh

# ── Env defaults ──────────────────────────────────────────────────────────────

DEFAULTS = {
    "host": os.getenv("SSH_DEFAULT_HOST", ""),
    "port": int(os.getenv("SSH_DEFAULT_PORT", "22")),
    "username": os.getenv("SSH_DEFAULT_USER", ""),
    "private_key_path": os.getenv("SSH_KEY_PATH", ""),
    "password": os.getenv("SSH_DEFAULT_PASSWORD", ""),
    "command_timeout": int(os.getenv("COMMAND_TIMEOUT", "30")),
}

ALLOWED_COMMANDS: list[str] = [
    c.strip()
    for c in os.getenv("ALLOWED_COMMANDS", "").split(",")
    if c.strip()
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _cfg(args: dict) -> SSHConfig:
    host = args.get("host") or DEFAULTS["host"]
    username = args.get("username") or DEFAULTS["username"]
    if not host:
        raise ValueError("SSH host required. Provide 'host' or set SSH_DEFAULT_HOST.")
    if not username:
        raise ValueError("SSH username required. Provide 'username' or set SSH_DEFAULT_USER.")
    return SSHConfig(
        host=host,
        username=username,
        port=int(args.get("port") or DEFAULTS["port"]),
        private_key_path=args.get("private_key_path") or DEFAULTS["private_key_path"] or None,
        passphrase=args.get("passphrase") or None,
        password=args.get("password") or DEFAULTS["password"] or None,
        command_timeout=DEFAULTS["command_timeout"],
    )


def _check_allowed(command: str) -> None:
    if not ALLOWED_COMMANDS:
        return
    base = command.strip().split()[0]
    if base not in ALLOWED_COMMANDS:
        raise ValueError(
            f"Command '{base}' is not allowed. "
            f"Allowed: {', '.join(ALLOWED_COMMANDS)}"
        )


def _q(value: Any) -> str:
    return shlex.quote(str(value))


def _exec(cfg: SSHConfig, command: str) -> CommandResult:
    _check_allowed(command)
    return ssh.execute(cfg, command)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _bool(args: dict, key: str, default: bool = False) -> bool:
    value = args.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


# ── Connection args schema (reused in all tools) ──────────────────────────────

_CONN_PROPS = {
    "host": {"type": "string", "description": "SSH host (overrides SSH_DEFAULT_HOST)"},
    "port": {"type": "integer", "description": "SSH port, default 22"},
    "username": {"type": "string", "description": "SSH user (overrides SSH_DEFAULT_USER)"},
    "private_key_path": {
        "type": "string",
        "description": "Path to private key, e.g. ~/.ssh/id_ed25519 (overrides SSH_KEY_PATH)",
    },
    "passphrase": {"type": "string", "description": "Passphrase for encrypted private key"},
    "password": {"type": "string", "description": "SSH password (fallback if no key)"},
}

# ── Tool schemas ──────────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "ssh_list_directory",
        "description": "List files and directories at a remote path via SFTP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Remote directory path (default: home directory)",
                    "default": ".",
                },
                **_CONN_PROPS,
            },
            "required": [],
        },
    },
    {
        "name": "ssh_read_file",
        "description": "Read the content of a file on the remote server via SFTP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute remote file path"},
                **_CONN_PROPS,
            },
            "required": ["path"],
        },
    },
    {
        "name": "ssh_write_file",
        "description": "Write or overwrite a file on the remote server via SFTP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute remote file path"},
                "content": {"type": "string", "description": "Content to write"},
                **_CONN_PROPS,
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "ssh_edit_file",
        "description": (
            "Edit a file on the remote server with targeted operations. "
            "Supports: replace (text substitution), insert_after/insert_before (add lines), "
            "delete_lines (remove by line numbers)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute remote file path"},
                "operation": {
                    "type": "string",
                    "enum": ["replace", "insert_after", "insert_before", "delete_lines"],
                    "description": "Edit operation type",
                },
                "old_text": {
                    "type": "string",
                    "description": "Text to find (required for replace)",
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text (required for replace, insert_after, insert_before)",
                },
                "line_number": {
                    "type": "integer",
                    "description": "Line number for insert operations (1-based)",
                },
                "line_numbers": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Line numbers to delete (1-based, for delete_lines)",
                },
                **_CONN_PROPS,
            },
            "required": ["path", "operation"],
        },
    },
    {
        "name": "ssh_tail_file",
        "description": "Read the last N lines of a remote file using tail.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "lines": {"type": "integer", "description": "Number of lines to return", "default": 100},
                **_CONN_PROPS,
            },
            "required": ["path"],
        },
    },
    {
        "name": "ssh_find_files",
        "description": "Find files or directories by name pattern under a root path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Root path to search from"},
                "name_pattern": {"type": "string", "description": "find -name pattern, e.g. '*.log'"},
                "file_type": {
                    "type": "string",
                    "enum": ["any", "file", "directory", "symlink"],
                    "description": "Filter by entry type",
                    "default": "any",
                },
                "max_depth": {"type": "integer", "description": "Optional max depth"},
                **_CONN_PROPS,
            },
            "required": ["root", "name_pattern"],
        },
    },
    {
        "name": "ssh_manage_service",
        "description": "Inspect or manage a systemd service: status, start, stop, restart, reload, enable, disable, logs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "systemd service name, e.g. nginx or ssh-mcp.service"},
                "action": {
                    "type": "string",
                    "enum": ["status", "start", "stop", "restart", "reload", "enable", "disable", "logs"],
                    "description": "Management action",
                },
                "lines": {"type": "integer", "description": "Log lines for action=logs", "default": 100},
                **_CONN_PROPS,
            },
            "required": ["service", "action"],
        },
    },
    {
        "name": "ssh_system_info",
        "description": (
            "Get a system overview from the remote server: "
            "OS, hostname, uptime, CPU, memory, disk usage."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {**_CONN_PROPS},
            "required": [],
        },
    },
    {
        "name": "ssh_execute",
        "description": (
            "Execute a shell command on a remote Linux server via SSH as a fallback tool for actions "
            "not covered by the structured tools. Returns stdout, stderr, exit code, and duration."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run, e.g. 'ls -la /var/log'",
                },
                **_CONN_PROPS,
            },
            "required": ["command"],
        },
    },
    {
        "name": "ssh_close_connection",
        "description": "Close the persistent SSH connection to free resources.",
        "inputSchema": {
            "type": "object",
            "properties": {**_CONN_PROPS},
            "required": [],
        },
    },
]

# ── Dispatch ──────────────────────────────────────────────────────────────────

def dispatch(name: str, args: dict) -> str:
    """Call the right tool and return a string result."""

    if name == "ssh_list_directory":
        cfg = _cfg(args)
        path = args.get("path", ".")
        entries = ssh.list_directory(cfg, path)
        lines = [
            f"{'d' if e['is_dir'] else '-'}  {e['name']:<42} {('<DIR>' if e['is_dir'] else str(e['size']) + 'B'):>12}"
            for e in entries
        ]
        return f"Directory: {path} on {cfg.host}\n\n" + "\n".join(lines)

    elif name == "ssh_read_file":
        return ssh.read_file(_cfg(args), args["path"])

    elif name == "ssh_write_file":
        ssh.write_file(_cfg(args), args["path"], args["content"])
        return f"✓ Written: {args['path']}"

    elif name == "ssh_edit_file":
        cfg = _cfg(args)
        result = ssh.edit_file(
            cfg=cfg,
            path=args["path"],
            operation=args["operation"],
            old_text=args.get("old_text"),
            new_text=args.get("new_text"),
            line_number=args.get("line_number"),
            line_numbers=args.get("line_numbers"),
        )
        return _json(result)

    elif name == "ssh_tail_file":
        cfg = _cfg(args)
        path = args["path"]
        lines = int(args.get("lines", 100))
        r = _exec(cfg, f"tail -n {lines} {_q(path)}")
        return r.stdout or r.stderr

    elif name == "ssh_find_files":
        cfg = _cfg(args)
        root = args["root"]
        pattern = args["name_pattern"]
        file_type = args.get("file_type", "any")
        max_depth = args.get("max_depth")
        type_flag = {"file": "f", "directory": "d", "symlink": "l"}.get(file_type)
        parts = ["find", _q(root)]
        if max_depth is not None:
            parts += ["-maxdepth", str(int(max_depth))]
        if type_flag:
            parts += ["-type", type_flag]
        parts += ["-name", _q(pattern), "|", "sort"]
        r = _exec(cfg, " ".join(parts))
        return r.stdout or r.stderr

    elif name == "ssh_manage_service":
        cfg = _cfg(args)
        service = args["service"]
        action = args["action"]
        lines = int(args.get("lines", 100))

        if action == "status":
            cmd = f"systemctl status {_q(service)} --no-pager -l"
        elif action == "start":
            cmd = f"systemctl start {_q(service)} && systemctl status {_q(service)} --no-pager -l"
        elif action == "stop":
            cmd = f"systemctl stop {_q(service)} && systemctl status {_q(service)} --no-pager -l"
        elif action == "restart":
            cmd = f"systemctl restart {_q(service)} && systemctl status {_q(service)} --no-pager -l"
        elif action == "reload":
            cmd = f"systemctl reload {_q(service)} && systemctl status {_q(service)} --no-pager -l"
        elif action == "enable":
            cmd = f"systemctl enable {_q(service)} && systemctl status {_q(service)} --no-pager -l"
        elif action == "disable":
            cmd = f"systemctl disable {_q(service)} && systemctl status {_q(service)} --no-pager -l"
        elif action == "logs":
            cmd = f"journalctl -u {_q(service)} -n {lines} --no-pager -l"
        else:
            raise ValueError(f"Unsupported service action: {action}")

        r = _exec(cfg, cmd)
        return r.stdout or r.stderr

    elif name == "ssh_system_info":
        cfg = _cfg(args)
        cmd = (
            "echo '── OS ──' && (cat /etc/os-release 2>/dev/null | grep PRETTY_NAME || uname -a) && "
            "echo '── Hostname ──' && hostname && "
            "echo '── Uptime / Load ──' && uptime && "
            "echo '── CPU ──' && nproc && grep 'model name' /proc/cpuinfo 2>/dev/null | head -1 || true && "
            "echo '── Memory ──' && free -h && "
            "echo '── Disk ──' && df -h --total 2>/dev/null | tail -1 || df -h | tail -1"
        )
        r = ssh.execute(cfg, cmd)
        return r.stdout or r.stderr

    elif name == "ssh_execute":
        _check_allowed(args["command"])
        cfg = _cfg(args)
        r: CommandResult = ssh.execute(cfg, args["command"])
        return _json({
            "stdout": r.stdout,
            "stderr": r.stderr,
            "exit_code": r.exit_code,
            "duration_ms": r.duration_ms,
            "host": cfg.host,
        })

    elif name == "ssh_close_connection":
        cfg = _cfg(args)
        ssh.close_client(cfg)
        return f"Connection to {cfg.host} closed."

    else:
        raise ValueError(f"Unknown tool: {name}")
