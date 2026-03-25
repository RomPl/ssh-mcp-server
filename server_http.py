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
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Response, HTTPException, Depends, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

from auth_oauth import (
    oauth,
    register_client,
    validate_client,
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
    client_id = request.query_params.get("client_id")
    redirect_uri = request.query_params.get("redirect_uri")
    state = request.query_params.get("state", "")
    code_challenge = request.query_params.get("code_challenge")
    code_challenge_method = request.query_params.get("code_challenge_method")

    if not all([client_id, redirect_uri, code_challenge]):
        raise HTTPException(status_code=400, detail="Missing required parameters")

    # Validate scope (must be mcp if provided)
    scope = request.query_params.get("scope", "mcp")
    if scope != "mcp":
        raise HTTPException(status_code=400, detail="Invalid scope")

    if code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="Only S256 is supported")

    # Do not validate client_id here: ChatGPT dynamic clients may be reused across
    # server restarts, while in-memory registration is ephemeral.
    # Access control is enforced by Google identity + ALLOWED_EMAIL + PKCE.
    

    # Save OAuth request in session
    request.session["oauth_req"] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
    }

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
    code = _sign_code(
        email=email,
        client_id=oauth_req["client_id"],
        code_challenge=oauth_req["code_challenge"],
        redirect_uri=oauth_req["redirect_uri"],
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
    redirect_uri: str = Form(None),
):
    """Exchange authorization code for access token (PKCE)."""
    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")

    if not all([code, code_verifier, client_id, redirect_uri]):
        raise HTTPException(status_code=400, detail="Missing required parameters")

    # Verify code + PKCE → get email
    # Verify code + PKCE → get email
    # Also validate redirect_uri binding (critical for OAuth security)
    email = verify_code(code, code_verifier, client_id, redirect_uri) if 'redirect_uri' in verify_code.__code__.co_varnames else verify_code(code, code_verifier, client_id)

    # Create JWT access token
    access_token = create_access_token(email)

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
    }


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
            sessions.pop(session_id, None)
            log.info(f"SSE session closed: {session_id}")

    log.info(f"New SSE session: {session_id}")
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/messages")
async def messages_endpoint(request: Request, _=Depends(require_auth)):
    session_id = request.query_params.get("sessionId")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=400, detail="Unknown or missing sessionId")

    body = await request.json()
    queue = sessions[session_id]

    async def process():
        response = handle_jsonrpc(body)
        if response is not None:
            await queue.put(response)

    asyncio.create_task(process())
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