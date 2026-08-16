"""
Firestore read/write for conversation records.

Collection structure:
  /conversations/{call_id}
    clientId        string   — from Rasen metadata.client_id
    callId          string
    callDate        string   — ISO timestamp
    status          string   — "completed" | "failed" | ...
    duration_ms     number
    transcript      array    — [{ turn_idx, user, agent }]
    recordingUrl    string | null
    extractedData   object   — from call.analyzed
    sentiment       object   — from call.analyzed
    hubspot_contact_id string | null
    hubspot_deal_id    string | null
    createdAt       timestamp
    updatedAt       timestamp

  /client_keys/{key}   (used for client dashboard auth lookup)
    clientId        string
    displayName     string
    active          boolean

On Cloud Run, uses Application Default Credentials (ADC) — no JSON key needed.
"""

from __future__ import annotations

import time
from typing import Any

from google.cloud import firestore
from loguru import logger

from server.core.config import FIREBASE_PROJECT_ID

# ── Singleton Firestore client ─────────────────────────────────────────────────
_db: firestore.AsyncClient | None = None


def get_db() -> firestore.AsyncClient:
    global _db
    if _db is None:
        _db = firestore.AsyncClient(project=FIREBASE_PROJECT_ID)
    return _db


# ── Seed helper (run once on startup) ────────────────────────────────────────

async def seed_demo_client_key():
    """
    Creates the wakilz_demo client key document if it doesn't exist yet.
    Idempotent — safe to call on every startup.
    """
    db = get_db()
    ref = db.collection("client_keys").document("wakilz_demo")
    snap = await ref.get()
    if not snap.exists:
        await ref.set({
            "clientId": "wakilz_demo",
            "displayName": "Wakilz Demo",
            "active": True,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        logger.info("firestore=seeded_demo_client_key")


# ── Conversation writes ───────────────────────────────────────────────────────

async def write_conversation(call_id: str, data: dict[str, Any]) -> None:
    """
    Upsert a conversation record on call.completed webhook.
    Creates the document if new, merges if it already exists (idempotent).
    """
    db = get_db()
    ref = db.collection("conversations").document(call_id)
    payload = {
        **data,
        "callId": call_id,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }
    # set with merge=True so re-delivery of the same event is safe
    await ref.set(payload, merge=True)
    logger.info(f"firestore=conversation_written call_id={call_id}")


async def update_analysis(
    call_id: str,
    extraction: dict[str, Any],
    sentiment: dict[str, Any],
) -> None:
    """
    Merge extraction + sentiment into an existing conversation record.
    Called on call.analyzed webhook.
    """
    db = get_db()
    ref = db.collection("conversations").document(call_id)
    await ref.set(
        {
            "extractedData": extraction,
            "sentiment": sentiment,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    logger.info(f"firestore=analysis_updated call_id={call_id}")


async def update_hubspot_ids(
    call_id: str,
    contact_id: str | None,
    deal_id: str | None,
) -> None:
    """Store HubSpot IDs back onto the conversation record."""
    db = get_db()
    ref = db.collection("conversations").document(call_id)
    update: dict[str, Any] = {"updatedAt": firestore.SERVER_TIMESTAMP}
    if contact_id:
        update["hubspot_contact_id"] = contact_id
    if deal_id:
        update["hubspot_deal_id"] = deal_id
    await ref.set(update, merge=True)


# ── Conversation reads ────────────────────────────────────────────────────────

async def list_conversations(
    client_id: str | None = None,
    limit: int = 50,
    start_after: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return conversations ordered by createdAt desc.
    If client_id is set → filter by clientId (client view).
    If client_id is None → return all (admin view).
    """
    db = get_db()
    col = db.collection("conversations")

    query = col.order_by("createdAt", direction=firestore.Query.DESCENDING)
    if client_id:
        query = query.where("clientId", "==", client_id)
    query = query.limit(limit)

    docs = query.stream()
    results = []
    async for doc in docs:
        results.append({"id": doc.id, **doc.to_dict()})
    return results


async def get_conversation(call_id: str) -> dict[str, Any] | None:
    """Return a single conversation by call_id."""
    db = get_db()
    doc = await db.collection("conversations").document(call_id).get()
    if not doc.exists:
        return None
    return {"id": doc.id, **doc.to_dict()}


# ── Client key lookup ─────────────────────────────────────────────────────────

async def get_client_by_key(key: str) -> dict[str, Any] | None:
    """
    Look up a client by their dashboard/embed key.
    The document ID in /client_keys/ IS the key.
    Returns { clientId, displayName, active } or None if not found.
    """
    db = get_db()
    doc = await db.collection("client_keys").document(key).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    if not data.get("active", True):
        return None
    return data
