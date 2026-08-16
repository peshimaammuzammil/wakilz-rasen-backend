"""
Short-lived JWT session tokens for the browser.

The browser calls GET /session to get a token, then presents it
as `Authorization: Bearer <token>` on POST /start and POST /sessions/{id}/api/offer.

This prevents unauthenticated public users from starting sessions directly.
On localhost the auth middleware bypasses this check for developer convenience.
"""

import time
from fastapi import APIRouter
import jwt

from server.core.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_SECONDS

router = APIRouter()


def issue_session_token() -> tuple[str, int]:
    """
    Create a short-lived JWT.
    Returns (token, expires_in_seconds).
    """
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + JWT_EXPIRE_SECONDS,
        "purpose": "voice_session",
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, JWT_EXPIRE_SECONDS


def verify_session_token(token: str) -> bool:
    """Return True if the token is valid and not expired."""
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return True
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False


@router.get("/session")
async def get_session():
    """
    Browser calls this first to get a short-lived JWT.
    Response: { token: string, expires_in: number }
    """
    token, expires_in = issue_session_token()
    return {"token": token, "expires_in": expires_in}
