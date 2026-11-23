"""Security, token parsing, and role-based scope enforcement."""
import base64
import hashlib
import hmac
import json
import time
from typing import Annotated, List, Optional
from fastapi import Depends, Header, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import ForbiddenException, UnauthorizedException


class TokenPayload(BaseModel):
    session_id: str
    user_id: str
    scope: str  # "user", "agent", "demo-control"
    exp: int


def generate_session_token(session_id: str, user_id: str, scope: str) -> str:
    """Generate a tamper-proof signed token for demo session access."""
    settings = get_settings()
    exp = int(time.time()) + (settings.SESSION_TOKEN_EXPIRE_HOURS * 3600)
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "scope": scope,
        "exp": exp,
    }
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_payload).decode("utf-8").rstrip("=")

    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        b64_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    b64_sig = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    return f"{b64_payload}.{b64_sig}"


def verify_session_token(token: str) -> TokenPayload:
    """Verify cryptographic signature and expiry of session token."""
    settings = get_settings()
    parts = token.split(".")
    if len(parts) != 2:
        raise UnauthorizedException("Malformed bearer token format.")

    b64_payload, b64_sig = parts

    # Recompute signature
    expected_sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        b64_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_b64_sig = (
        base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")
    )

    if not hmac.compare_digest(b64_sig, expected_b64_sig):
        raise UnauthorizedException("Invalid token signature.")

    # Decode payload
    padding = "=" * ((4 - len(b64_payload) % 4) % 4)
    try:
        raw_payload = base64.urlsafe_b64decode(b64_payload + padding)
        data = json.loads(raw_payload.decode("utf-8"))
    except Exception:
        raise UnauthorizedException("Corrupt token payload.")

    exp = data.get("exp", 0)
    if time.time() > exp:
        raise UnauthorizedException("Token has expired.")

    return TokenPayload(**data)


def get_current_token_payload(
    authorization: Annotated[Optional[str], Header()] = None,
) -> TokenPayload:
    """FastAPI dependency to extract and verify the bearer token."""
    if not authorization:
        raise UnauthorizedException("Missing Authorization header.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedException("Authorization header must be 'Bearer <token>'.")

    return verify_session_token(token)


class ScopeChecker:
    """Enforces required scopes. If required scope is 'user', 'agent' is rejected."""

    def __init__(self, allowed_scopes: List[str]):
        self.allowed_scopes = allowed_scopes

    def __call__(
        self, payload: Annotated[TokenPayload, Depends(get_current_token_payload)]
    ) -> TokenPayload:
        if payload.scope not in self.allowed_scopes:
            raise ForbiddenException(
                f"Action requires one of scopes {self.allowed_scopes}, but token holds scope '{payload.scope}'."
            )
        return payload


# Dependency shortcuts
require_user_scope = ScopeChecker(["user"])
require_agent_or_user_scope = ScopeChecker(["user", "agent"])
require_demo_control_scope = ScopeChecker(["demo-control"])
require_any_scope = ScopeChecker(["user", "agent", "demo-control"])
