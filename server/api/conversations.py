"""
Conversations API — reads call records from Firestore.

Endpoints:
  GET /api/conversations          → paginated list (scoped by clientId or all for admin)
  GET /api/conversations/{id}     → single conversation detail
  GET /api/conversations/{id}/audio → fresh signed recording URL from Rasen

Access control:
  Admin: passes Firebase ID token (Authorization: Bearer <firebase_id_token>)
         OR uses X-Admin-Key header (matching ADMIN_API_KEY env var for simple setups)
  Client: passes client dashboard JWT from /api/client/verify
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Query
from loguru import logger

from server.api.client_auth import decode_client_token
from server.core.config import JWT_SECRET
from server.services.firestore_db import get_conversation, list_conversations
from server.services.rasen_client import get_rasen_client

router = APIRouter()

# Simple admin API key for non-Firebase admin access (optional)
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


def _resolve_access(
    authorization: str | None,
    x_admin_key: str | None,
) -> tuple[str | None, bool]:
    """
    Resolve who is calling and what they can access.

    Returns:
      (client_id, is_admin)
      client_id is None for admins (they can see all)
      is_admin=True means unrestricted access
    """
    # ── Admin key (simple, for dashboard backend calls) ────────────────────
    if x_admin_key and ADMIN_API_KEY and x_admin_key == ADMIN_API_KEY:
        return None, True

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = authorization.split(" ", 1)[1]

    # ── Client dashboard JWT ───────────────────────────────────────────────
    client_payload = decode_client_token(token)
    if client_payload:
        return client_payload["client_id"], False

    # ── Firebase ID token (for admin dashboard) ────────────────────────────
    # We verify the Firebase token by calling Firebase's tokeninfo endpoint.
    # This avoids needing the Admin SDK on the conversations endpoint.
    try:
        resp = httpx.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={token}",
            timeout=5.0,
        )
        if resp.status_code == 200:
            claims = resp.json()
            # Check it's from our Firebase project
            aud = claims.get("aud", "")
            if "wakilz-dasboard" in aud or "wakilz" in aud.lower():
                # It's a valid Firebase token — treat as admin
                return None, True
    except Exception as e:
        logger.debug(f"conversations=firebase_token_check_failed error={e!r}")

    raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/conversations")
async def get_conversations(
    limit: int = Query(default=50, le=200),
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    """
    List conversations.
    - Admin: returns all conversations across all clients
    - Client: returns only conversations where clientId matches
    """
    client_id, is_admin = _resolve_access(authorization, x_admin_key)

    try:
        conversations = await list_conversations(
            client_id=None if is_admin else client_id,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"conversations=list_failed error={e!r}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")

    return {
        "conversations": conversations,
        "count": len(conversations),
        "is_admin": is_admin,
    }


@router.get("/api/conversations/{call_id}")
async def get_conversation_detail(
    call_id: str,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    """Single conversation detail including full transcript + extraction."""
    client_id, is_admin = _resolve_access(authorization, x_admin_key)

    try:
        conv = await get_conversation(call_id)
    except Exception as e:
        logger.error(f"conversations=get_failed call_id={call_id} error={e!r}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversation")

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Enforce client scoping
    if not is_admin and conv.get("clientId") != client_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return conv


@router.get("/api/conversations/{call_id}/audio")
async def get_conversation_audio(
    call_id: str,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    """
    Returns a fresh signed URL for the call recording from Rasen.
    Rasen's signed URLs are short-lived — always fetch fresh, never store.
    """
    client_id, is_admin = _resolve_access(authorization, x_admin_key)

    # Verify access to this call
    if not is_admin:
        conv = await get_conversation(call_id)
        if not conv or conv.get("clientId") != client_id:
            raise HTTPException(status_code=403, detail="Access denied")

    rasen = get_rasen_client()
    try:
        url = await rasen.get_call_recording_url(call_id)
    except Exception as e:
        logger.error(f"conversations=audio_failed call_id={call_id} error={e!r}")
        raise HTTPException(status_code=502, detail="Failed to fetch recording URL")

    if not url:
        raise HTTPException(status_code=404, detail="Recording not available")

    return {"url": url, "call_id": call_id}
