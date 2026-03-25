#!/usr/bin/env python3
"""
server_stdio.py — MCP server over stdio transport.
Use this for Claude Desktop.

Usage:
    python server_stdio.py
"""

import asyncio
import json
import sys
import logging

from dotenv import load_dotenv
load_dotenv()

import tools as t
import ssh_client as ssh

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

# ── Raw JSON-RPC over stdio ───────────────────────────────────────────────────
# We implement the MCP protocol manually to avoid any dependency version issues.

def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}

def _err(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

def handle(msg: dict) -> dict | None:
    method = msg.get("method", "")
    req_id = msg.get("id")

    if method == "initialize":
        return _ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ssh-mcp-server", "version": "1.0.0"},
        })

    if method == "notifications/initialized":
        return None  # no response for notifications

    if method == "tools/list":
        return _ok(req_id, {"tools": t.TOOLS})

    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            result = t.dispatch(name, args)
            return _ok(req_id, {"content": [{"type": "text", "text": result}]})
        except Exception as e:
            return _ok(req_id, {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            })

    if method == "ping":
        return _ok(req_id, {})

    return _err(req_id, -32601, f"Method not found: {method}")


def main():
    sys.stderr.write("SSH MCP Server (stdio) started\n")
    sys.stderr.flush()

    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer

    while True:
        try:
            line = stdin.readline()
            if not line:
                break
            msg = json.loads(line.decode("utf-8"))
            response = handle(msg)
            if response is not None:
                out = json.dumps(response, ensure_ascii=False) + "\n"
                stdout.write(out.encode("utf-8"))
                stdout.flush()
        except json.JSONDecodeError as e:
            sys.stderr.write(f"JSON parse error: {e}\n")
        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f"Unexpected error: {e}\n")

    ssh.close_all()


if __name__ == "__main__":
    main()
