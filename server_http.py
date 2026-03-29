#!/usr/bin/env python3
"""
SSH MCP Server — HTTP+SSE with MCP OAuth 2.1 authorization.

Endpoints:
  /.well-known/oauth-protected-resource   — Protected Resource Metadata
  /.well-known/oauth-authorization-server — Authorization Server Metadata
  /.well-known/openid-configuration       — Alias for above
  /register                               — Dynamic Client Registration
  /authorize                              — Start OAuth flow (redirect to Google)
  /google/callback                        — Google callback, issue auth code
  /token                                  — Exchange code for access token (PKCE)
  /health                                 — Health check
  /sse                                    — SSE endpoint (requires token)
  /messages                               — JSON-RPC endpoint (requires token)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
import argparse
import logging
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Response, HTTPException, Depends, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
from pydantic import BaseModel, Field

from auth_oauth import (
    oauth,
    register_client,
    validate_client,
    validate_chatgpt_client_secret,
    validate_chatgpt_redirect_uri,
    is_chatgpt_static_client_configured,
    CHATGPT_CLIENT_ID,
    _sign_code,
    verify_code,
    create_access_token,
    require_auth,
    PUBLIC_BASE_URL,
    ALLOWED_EMAIL,
)
import tools as t
import ssh_client as ssh

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
log = logging.getLogger("ssh-mcp-http")

SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET is required")

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="SSH MCP Server", version="2.0.0")

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Minimal logging (no headers!) ─────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    log.info(f"{request.method} {request.url.path}")
    return await call_next(request)

# ── Session store (SSE queues) ────────────────────────────────────────────────

sessions: dict[str, asyncio.Queue] = {}

# ── JSON-RPC helpers ──────────────────────────────────────────────────────────

def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_jsonrpc(msg: dict) -> dict | None:
    method = msg.get("method", "")
    req_id = msg.get("id")

    if method == "initialize":
        return _ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ssh-mcp-server", "version": "2.0.0"},
        })

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None

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




class RestToolRequest(BaseModel):
    arguments: dict = Field(default_factory=dict)


class ShellRequest(BaseModel):
    command: str
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    connect_timeout: Optional[int] = None
    command_timeout: Optional[int] = None
    private_key_path: Optional[str] = None
    passphrase: Optional[str] = None
    password: Optional[str] = None


def _parse_tool_result(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _dispatch_rest_tool(name: str, arguments: dict):
    result = t.dispatch(name, arguments)
    return {
        "ok": True,
        "tool": name,
        "result": _parse_tool_result(result),
    }



# ── REST API bridge for GPT Actions ───────────────────────────────────────────

def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = {
        "openapi": "3.1.0",
        "info": {
            "title": "SSH MCP REST Bridge",
            "description": (
                "REST bridge over the existing SSH MCP tools for GPT Actions and other OpenAPI clients."
            ),
            "version": "1.0.0",
        },
        "servers": [{"url": PUBLIC_BASE_URL}],
        "paths": {
            "/health": {
                "get": {
                    "operationId": "getHealth",
                    "description": "Health check",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/shell": {
                "post": {
                    "operationId": "runShellCommand",
                    "description": "Execute a shell command on the remote Linux server via SSH.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "command": {"type": "string"},
                                        "host": {"type": "string"},
                                        "port": {"type": "integer"},
                                        "username": {"type": "string"},
                                        "connect_timeout": {"type": "integer"},
                                        "command_timeout": {"type": "integer"},
                                        "private_key_path": {"type": "string"},
                                        "passphrase": {"type": "string"},
                                        "password": {"type": "string"},
                                    },
                                    "required": ["command"],
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Command result"}},
                }
            },
            "/tool/{name}": {
                "post": {
                    "operationId": "callTool",
                    "description": (
                        "Call any existing MCP SSH tool by name with the same arguments as the MCP tool schema."
                    ),
                    "parameters": [
                        {
                            "name": "name",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "arguments": {
                                            "type": "object",
                                            "additionalProperties": True,
                                        }
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Tool result"}},
                }
            },
        },
    }

    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi


@app.post("/shell")
async def shell_endpoint(req: ShellRequest, user=Depends(require_auth)):
    args = req.dict(exclude_none=True)
    result = t.dispatch("ssh_execute", args)
    parsed = _parse_tool_result(result)
    if isinstance(parsed, dict):
        return JSONResponse(parsed)
    return JSONResponse({"ok": True, "stdout": str(parsed), "stderr": "", "code": 0})


@app.post("/tool/{name}")
@app.post("/tools/{name}")
async def tool_bridge_endpoint(name: str, req: Optional[RestToolRequest] = None, user=Depends(require_auth)):
    tool_names = {tool["name"] for tool in t.TOOLS}
    if name not in tool_names:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")
    arguments = req.arguments if req else {}
    return JSONResponse(_dispatch_rest_tool(name, arguments))

# ── OAuth Discovery ───────────────────────────────────────────────────────────

@app.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata():
    return {
        "resource": PUBLIC_BASE_URL,
        "authorization_servers": [PUBLIC_BASE_URL],
        "scopes_supported": ["mcp"],
        "bearer_methods_supported": ["header"],
    }


@app.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata():
    return {
        "issuer": PUBLIC_BASE_URL,
        "authorization_endpoint": f"{PUBLIC_BASE_URL}/authorize",
        "token_endpoint": f"{PUBLIC_BASE_URL}/token",
        "registration_endpoint": f"{PUBLIC_BASE_URL}/register",
        "scopes_supported": ["mcp"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
    }


@app.get("/.well-known/openid-configuration")
async def openid_configuration():
    """Alias for authorization server metadata (OIDC compatibility)."""
    return await authorization_server_metadata()


# ── Dynamic Client Registration ───────────────────────────────────────────────

@app.post("/register")
async def register_endpoint(request: Request):
    body = await request.json()
    redirect_uris = body.get("redirect_uris", [])
    if not redirect_uris:
        raise HTTPException(status_code=400, detail="redirect_uris required")
    return register_client(redirect_uris)


# ── Authorization Flow ────────────────────────────────────────────────────────

@app.get("/authorize")
async def authorize(request: Request):
    """
    Start OAuth authorization flow.
    Expects: client_id, redirect_uri, state, code_challenge, code_challenge_method
    Redirects to Google OAuth.
    """
    response_type = request.query_params.get("response_type") or "code"
    client_id = request.query_params.get("client_id")
    redirect_uri = request.query_params.get("redirect_uri")
    state = request.query_params.get("state", "")
    code_challenge = request.query_params.get("code_challenge")
    code_challenge_method = request.query_params.get("code_challenge_method")

    is_static = bool(
        is_chatgpt_static_client_configured() and client_id and client_id == CHATGPT_CLIENT_ID
    )

    missing = []
    if not client_id:
        missing.append("client_id")
    if not redirect_uri:
        missing.append("redirect_uri")
    if not is_static:
        if not code_challenge:
            missing.append("code_challenge")
        if not code_challenge_method:
            missing.append("code_challenge_method")
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required parameters: {', '.join(missing)}",
        )

    if response_type != "code":
        raise HTTPException(status_code=400, detail="Invalid response_type (expected 'code')")

    # Validate scope (must be mcp if provided)
    scope = request.query_params.get("scope")
    if not scope:
        scope = "mcp"
    if scope != "mcp":
        raise HTTPException(status_code=400, detail="Invalid scope")

    if not is_static:
        if code_challenge_method != "S256":
            raise HTTPException(status_code=400, detail="Only S256 is supported")

    if is_chatgpt_static_client_configured() and client_id == CHATGPT_CLIENT_ID:
        if not validate_client(client_id, redirect_uri):
            raise HTTPException(status_code=400, detail="Invalid client_id or redirect_uri for static client")

    # Note: for non-static clients we intentionally don't enforce in-memory registration
    # here, because dynamic registration is ephemeral. Access control is enforced by
    # Google identity + ALLOWED_EMAIL + PKCE.
    

    # Save OAuth request in session
    request.session["oauth_req"] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if code_challenge:
        request.session["oauth_req"]["code_challenge"] = code_challenge

    # Redirect to Google
    google_redirect_uri = f"{PUBLIC_BASE_URL}/google/callback"
    return await oauth.google.authorize_redirect(request, google_redirect_uri)


@app.get("/google/callback")
async def google_callback(request: Request):
    """Handle Google OAuth callback, issue authorization code."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        log.error(f"Google OAuth error: {e}")
        raise HTTPException(status_code=401, detail="Google authentication failed")

    user = token.get("userinfo") or {}
    email = user.get("email")

    if not email:
        raise HTTPException(status_code=401, detail="Email not provided by Google")

    if email != ALLOWED_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Get OAuth request from session
    oauth_req = request.session.get("oauth_req")
    if not oauth_req:
        raise HTTPException(status_code=400, detail="Missing OAuth request in session")

    # Validate state (basic CSRF protection)
    if "state" not in oauth_req:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    # Generate authorization code
    code_challenge = oauth_req.get("code_challenge")
    code = _sign_code(
        email=email,
        client_id=oauth_req["client_id"],
        redirect_uri=oauth_req["redirect_uri"],
        code_challenge=code_challenge,
    )

    # Redirect back to client
    redirect_uri = oauth_req["redirect_uri"]
    state = oauth_req["state"]
    sep = "&" if "?" in redirect_uri else "?"
    url = f"{redirect_uri}{sep}code={code}"
    if state:
        url += f"&state={state}"

    # Clear session
    request.session.pop("oauth_req", None)

    return Response(
        status_code=302,
        headers={"Location": url},
    )


# ── Token Endpoint ────────────────────────────────────────────────────────────

@app.post("/token")
async def token_endpoint(
    grant_type: str = Form(...),
    code: str = Form(None),
    code_verifier: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
    redirect_uri: str = Form(None),
    refresh_token: str = Form(None),
):
    if grant_type == "authorization_code":
        missing = []
        if not code:
            missing.append("code")
        if not client_id:
            missing.append("client_id")
        if not redirect_uri:
            missing.append("redirect_uri")
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required parameters: {', '.join(missing)}",
            )

        validate_chatgpt_redirect_uri(client_id, redirect_uri)
        validate_chatgpt_client_secret(client_id, client_secret)

        email = verify_code(code, code_verifier, client_id, redirect_uri)

        access_token = create_access_token(email)

        from auth_oauth import create_refresh_token
        new_refresh_token = create_refresh_token(email)

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "Bearer",
            "expires_in": 86400,
        }

    elif grant_type == "refresh_token":
        from auth_oauth import _refresh_tokens

        data = _refresh_tokens.get(refresh_token)
        if not data:
            raise HTTPException(status_code=401, detail="Invalid refresh_token")

        email = data["email"]
        access_token = create_access_token(email)

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 86400,
        }

    else:
        raise HTTPException(status_code=400, detail="Unsupported grant_type")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "auth": "oauth2.1"}


# ── MCP Endpoints (protected) ─────────────────────────────────────────────────

def _unauthorized_response():
    """Return 401 with WWW-Authenticate header per MCP spec."""
    return Response(
        status_code=401,
        headers={
            "WWW-Authenticate": (
                f'Bearer realm="mcp", '
                f'resource_metadata="{PUBLIC_BASE_URL}/.well-known/oauth-protected-resource"'
            )
        },
    )


@app.get("/sse")
async def sse_endpoint(request: Request):
    # Check auth manually to return proper 401
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return _unauthorized_response()
    token = auth.split(" ", 1)[1]
    try:
        from auth_oauth import verify_access_token
        verify_access_token(token)
    except HTTPException:
        return _unauthorized_response()

    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    sessions[session_id] = queue

    endpoint_url = f"/messages?sessionId={session_id}"

    async def event_stream() -> AsyncGenerator[str, None]:
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    if msg is None:
                        break
                    data = json.dumps(msg, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            # не удаляем сессию — иначе ChatGPT теряет её при reconnect
            log.info(f"SSE session closed (kept): {session_id}")

    log.info(f"New SSE session: {session_id}")
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/messages")
async def messages_endpoint(request: Request, _=Depends(require_auth)):
    session_id = request.query_params.get("sessionId")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=400, detail="Unknown or missing sessionId")

    body = await request.json()
    queue = sessions[session_id]

    async def process_in_background() -> None:
        try:
            # tools/call выполняет блокирующий SSH (paramiko).
            # Важно не блокировать event loop: иначе ChatGPT получает TimeoutError на /messages.
            response = await asyncio.to_thread(handle_jsonrpc, body)
        except Exception as e:
            req_id = body.get("id")
            response = _ok(req_id, {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            })

        if response is not None:
            await queue.put(response)

    asyncio.create_task(process_in_background())
    return Response(status_code=202)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("HTTP_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("HTTP_PORT", "3000")))
    args = parser.parse_args()

    log.info(f"Server running on http://{args.host}:{args.port}")
    log.info(f"Public URL: {PUBLIC_BASE_URL}")
    log.info("Auth: OAuth 2.1 with PKCE (Google)")

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        ssh.close_all()


if __name__ == "__main__":
    main()
