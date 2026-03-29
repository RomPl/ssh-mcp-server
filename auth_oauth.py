# auth_oauth.py — MCP OAuth 2.1 authorization with Google as identity provider
"""
Implements:
- OAuth 2.1 with PKCE (S256)
- Dynamic Client Registration
- HMAC-signed authorization codes
- JWT access tokens (HS256)
- Google OAuth as identity provider
- Protected Resource Metadata & Authorization Server Metadata
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Optional

import jwt
from fastapi import Request, HTTPException
from authlib.integrations.starlette_client import OAuth

# ── ENV validation ────────────────────────────────────────────────────────────

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
ALLOWED_EMAIL = os.getenv("ALLOWED_EMAIL", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
OAUTH_CODE_SECRET = os.getenv("OAUTH_CODE_SECRET", "")

CHATGPT_CLIENT_ID = os.getenv("CHATGPT_CLIENT_ID", "")
CHATGPT_CLIENT_SECRET = os.getenv("CHATGPT_CLIENT_SECRET", "")
CHATGPT_REDIRECT_URI = os.getenv("CHATGPT_REDIRECT_URI", "")

_missing = []
if not PUBLIC_BASE_URL:
    _missing.append("PUBLIC_BASE_URL")
if not GOOGLE_CLIENT_ID:
    _missing.append("GOOGLE_CLIENT_ID")
if not GOOGLE_CLIENT_SECRET:
    _missing.append("GOOGLE_CLIENT_SECRET")
if not ALLOWED_EMAIL:
    _missing.append("ALLOWED_EMAIL")
if not JWT_SECRET:
    _missing.append("JWT_SECRET")
if not OAUTH_CODE_SECRET:
    _missing.append("OAUTH_CODE_SECRET")
if _missing:
    raise RuntimeError(f"Missing required env vars: {', '.join(_missing)}")

# ── Google OAuth client ───────────────────────────────────────────────────────

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ── Dynamic Client Registration (in-memory) ───────────────────────────────────

_clients: dict[str, dict] = {}


def register_client(redirect_uris: list[str]) -> dict:
    """Register a new OAuth client and return credentials."""
    client_id = uuid.uuid4().hex
    client_secret = uuid.uuid4().hex + uuid.uuid4().hex
    _clients[client_id] = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uris": redirect_uris,
        "created_at": int(time.time()),
    }
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": "client_secret_post",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
    }


def validate_client(client_id: str, redirect_uri: str) -> bool:
    """Validate client_id and redirect_uri."""
    if (
        CHATGPT_CLIENT_ID
        and CHATGPT_CLIENT_SECRET
        and CHATGPT_REDIRECT_URI
        and client_id == CHATGPT_CLIENT_ID
    ):
        return redirect_uri == CHATGPT_REDIRECT_URI

    client = _clients.get(client_id)
    if not client:
        return False
    return redirect_uri in client["redirect_uris"]


# ── Authorization code (HMAC-signed, stateless) ──────────────────────────────

def _sign_code(
    email: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: Optional[str] = None,
) -> str:
    """Create HMAC-signed authorization code."""
    payload = {
        "email": email,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "iat": int(time.time()),
    }
    if code_challenge:
        payload["code_challenge"] = code_challenge
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(OAUTH_CODE_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    # code = base64url(payload) + "." + signature
    import base64
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"{encoded}.{sig}"


def verify_code(
    code: str,
    code_verifier: Optional[str],
    client_id: str,
    redirect_uri: Optional[str] = None,
) -> str:
    """
    Verify authorization code + PKCE.
    Returns email if valid, raises HTTPException otherwise.
    """
    import base64

    try:
        parts = code.split(".", 1)
        if len(parts) != 2:
            raise ValueError("bad format")
        encoded, sig = parts

        # Reconstruct raw
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        raw = base64.urlsafe_b64decode(encoded).decode()

        # Verify HMAC
        expected_sig = hmac.new(
            OAUTH_CODE_SECRET.encode(), raw.encode(), hashlib.sha256
        ).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("invalid signature")

        payload = json.loads(raw)

        # Check TTL (5 minutes)
        if int(time.time()) - payload["iat"] > 300:
            raise ValueError("code expired")

        # Check client_id
        if payload["client_id"] != client_id:
            raise ValueError("client_id mismatch")

        # Check redirect_uri binding (if provided)
        if redirect_uri is not None:
            if payload.get("redirect_uri") != redirect_uri:
                raise ValueError("redirect_uri mismatch")

        challenge = payload.get("code_challenge")
        if challenge:
            if not code_verifier:
                raise ValueError("Missing code_verifier")
            digest = hashlib.sha256(code_verifier.encode()).digest()
            import base64 as b64
            computed = b64.urlsafe_b64encode(digest).decode().rstrip("=")
            if not hmac.compare_digest(computed, challenge):
                raise ValueError("PKCE verification failed")
        else:
            # Allow no-PKCE only for configured static ChatGPT client.
            if not is_chatgpt_static_client(payload["client_id"]):
                raise ValueError("PKCE is required for this client")

        return payload["email"]

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid code: {e}")


def is_chatgpt_static_client_configured() -> bool:
    return bool(CHATGPT_CLIENT_ID and CHATGPT_CLIENT_SECRET and CHATGPT_REDIRECT_URI)


def is_chatgpt_static_client(client_id: str) -> bool:
    return is_chatgpt_static_client_configured() and client_id == CHATGPT_CLIENT_ID


def validate_chatgpt_redirect_uri(client_id: str, redirect_uri: str) -> None:
    if not is_chatgpt_static_client(client_id):
        return
    if redirect_uri != CHATGPT_REDIRECT_URI:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid redirect_uri for static client. "
                "Expected CHATGPT_REDIRECT_URI exactly."
            ),
        )


def validate_chatgpt_client_secret(client_id: str, client_secret: Optional[str]) -> None:
    if not is_chatgpt_static_client(client_id):
        return
    if not client_secret:
        raise HTTPException(status_code=401, detail="Missing client_secret for static client")
    if not hmac.compare_digest(client_secret, CHATGPT_CLIENT_SECRET):
        raise HTTPException(status_code=401, detail="Invalid client_secret for static client")


# ── JWT access token ─────────────────────────────────────────────────────────

_refresh_tokens: dict[str, dict] = {}

def create_access_token(email: str) -> str:
    """Create JWT access token (HS256, 1 hour)."""
    now = int(time.time())
    payload = {
        "iss": PUBLIC_BASE_URL,
        "sub": email,
        "aud": PUBLIC_BASE_URL,
        "email": email,
        "scope": "mcp",
        "iat": now,
        "exp": now + 604800,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def create_refresh_token(email: str) -> str:
    token = uuid.uuid4().hex + uuid.uuid4().hex
    _refresh_tokens[token] = {
        "email": email,
        "created_at": int(time.time()),
    }
    return token    

def verify_access_token(token: str) -> dict:
    """Verify JWT access token. Returns payload if valid."""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            audience=PUBLIC_BASE_URL,
            issuer=PUBLIC_BASE_URL,
        )
        if payload.get("email") != ALLOWED_EMAIL:
            raise HTTPException(status_code=403, detail="Forbidden")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ── FastAPI dependency ────────────────────────────────────────────────────────

def require_auth(request: Request) -> dict:
    """FastAPI dependency: extract and verify Bearer token."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing token",
            headers={
                "WWW-Authenticate": (
                    f'Bearer realm="mcp", '
                    f'resource_metadata="{PUBLIC_BASE_URL}/.well-known/oauth-protected-resource"'
                )
            },
        )
    token = auth.split(" ", 1)[1]
    return verify_access_token(token)
