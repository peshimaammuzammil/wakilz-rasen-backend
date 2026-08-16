"""
Client dashboard authentication via secret key.

GET /api/client/verify?key=wklz_...

The browser sends the client's secret key.
Backend looks it up in Firestore /client_keys/{key}.
Returns a scoped JWT containing the clientId — used for subsequent
/api/conversations requests.

This is separate from Firebase Auth (which is admin-only).
Clients don't need to sign in — they just use their secret key URL.
"""

from __future__ import annotations

import time

import jwt
from fastapi import APIRouter, HTTPException
from loguru import logger

from server.core.config import JWT_SECRET, JWT_ALGORITHM
from server.services.firestore_db import get_client_by_key

router = APIRouter()


def _issue_client_token(client_id: str, display_name: str) -> str:
    """Issue a scoped JWT for a client (24h validity for dashboard sessions)."""
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + 86400,  # 24 hours
        "purpose": "client_dashboard",
        "client_id": client_id,
        "display_name": display_name,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_client_token(token: str) -> dict | None:
    """Decode and validate a client dashboard JWT. Returns payload or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("purpose") != "client_dashboard":
            return None
        return payload
    except jwt.InvalidTokenError:
        return None


@router.get("/api/client/verify")
async def verify_client_key(key: str):
    """
    Browser calls: GET /api/client/verify?key=wklz_abc123
    Returns: { token, clientId, displayName }

    The token is then used as Authorization: Bearer <token>
    on GET /api/conversations requests.
    """
    if not key:
        raise HTTPException(status_code=400, detail="key parameter is required")

    client = await get_client_by_key(key)
    if not client:
        logger.warning(f"client_auth=invalid_key key_prefix={key[:8]}...")
        raise HTTPException(status_code=401, detail="Invalid or inactive client key")

    client_id = client["clientId"]
    display_name = client.get("displayName", client_id)
    token = _issue_client_token(client_id, display_name)

    logger.info(f"client_auth=verified client_id={client_id}")
    return {
        "token": token,
        "clientId": client_id,
        "displayName": display_name,
    }
