"""
Rasen webhook receiver.

POST /webhooks/rasen

Events handled:
  call.completed  → write call record + transcript to Firestore
  call.analyzed   → fetch full analysis, update Firestore + sync to HubSpot

Signature verification:
  Enabled when RASEN_WEBHOOK_SECRET is set.
  Skipped (with warning) when not set (dev mode).

Delivery semantics (Rasen):
  - At-least-once: deduplicate on X-Rasen-Delivery header
  - Retry ladder: 10s → 1m → 5m → 30m → 2h
  - Always respond 2xx fast, then process async
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, Request, Response
from loguru import logger

from server.services.firestore_db import (
    get_conversation,
    update_analysis,
    update_hubspot_ids,
    write_conversation,
)
from server.services.hubspot import sync_call_to_hubspot
from server.services.rasen_client import get_rasen_client
from server.utils.webhook_verify import verify_rasen_signature

router = APIRouter()

# Simple in-memory dedup set for X-Rasen-Delivery IDs
# Bounded to last 1000 deliveries to avoid unbounded growth
_seen_deliveries: dict[str, bool] = {}
_MAX_SEEN = 1000


def _is_duplicate(delivery_id: str) -> bool:
    if delivery_id in _seen_deliveries:
        return True
    if len(_seen_deliveries) >= _MAX_SEEN:
        # Evict oldest ~10% when full
        keys = list(_seen_deliveries.keys())
        for k in keys[:100]:
            del _seen_deliveries[k]
    _seen_deliveries[delivery_id] = True
    return False


# ── Background processors ─────────────────────────────────────────────────────

async def _process_call_completed(call: dict[str, Any]) -> None:
    """
    On call.completed:
    - Write transcript + status + metadata to Firestore
    """
    call_id = call.get("id", "")
    if not call_id:
        logger.warning("webhook=call_completed missing call.id")
        return

    # Extract client_id from metadata
    metadata = call.get("metadata", {}) or {}
    client_id = metadata.get("client_id", "wakilz_demo")

    # Build transcript list
    raw_transcript = call.get("transcript", []) or []
    transcript = [
        {
            "turn_idx": t.get("turn_idx", i),
            "agent": t.get("agent", ""),
            "user": t.get("user", ""),
        }
        for i, t in enumerate(raw_transcript)
    ]

    doc = {
        "clientId": client_id,
        "status": call.get("detailed_status", call.get("status", "completed")),
        "direction": call.get("direction", "inbound"),
        "duration_ms": call.get("duration_ms"),
        "transcript": transcript,
        "recordingUrl": call.get("recording_url"),  # webhook payload has a usable signed URL
        "agentId": call.get("agent_id"),
        "agentVersionNo": call.get("agent_version_no"),
        "startedAt": call.get("started_at"),
        "endedAt": call.get("ended_at"),
        "variables": call.get("variables", {}),
        "metadata": metadata,
        "createdAt": call.get("started_at"),
    }

    try:
        await write_conversation(call_id, doc)
        logger.info(f"webhook=call_completed_processed call_id={call_id} client_id={client_id}")
    except Exception as e:
        logger.error(f"webhook=firestore_write_failed call_id={call_id} error={e!r}")


async def _process_call_analyzed(call: dict[str, Any], analysis_block: dict[str, Any]) -> None:
    """
    On call.analyzed:
    - Fetch full analysis from Rasen API (the webhook only sends a summary)
    - Update Firestore with extraction + sentiment
    - Sync to HubSpot (contact + deal)
    """
    call_id = call.get("id", "")
    if not call_id:
        logger.warning("webhook=call_analyzed missing call.id")
        return

    rasen = get_rasen_client()

    # Fetch full analysis (webhook payload only has a summary block)
    try:
        full_analysis = await rasen.get_call_analysis(call_id)
        extraction = full_analysis.extraction
        sentiment = full_analysis.sentiment
    except Exception as e:
        logger.error(f"webhook=analysis_fetch_failed call_id={call_id} error={e!r}")
        # Fall back to what the webhook gave us
        extraction = analysis_block.get("extraction", {})
        sentiment = analysis_block.get("sentiment", {})

    # Update Firestore
    try:
        await update_analysis(call_id, extraction, sentiment)
        logger.info(f"webhook=analysis_updated call_id={call_id}")
    except Exception as e:
        logger.error(f"webhook=analysis_update_failed call_id={call_id} error={e!r}")

    # Sync to HubSpot
    metadata = call.get("metadata", {}) or {}
    try:
        contact_id, deal_id = await sync_call_to_hubspot(call_id, extraction, metadata)
        if contact_id or deal_id:
            await update_hubspot_ids(call_id, contact_id, deal_id)
    except Exception as e:
        logger.error(f"webhook=hubspot_sync_failed call_id={call_id} error={e!r}")


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/webhooks/rasen", status_code=200)
async def rasen_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_rasen_signature: str | None = Header(default=None),
    x_rasen_delivery: str | None = Header(default=None),
    x_rasen_event: str | None = Header(default=None),
):
    """
    Receives all Rasen webhook events.
    Responds 200 immediately; heavy processing happens in background.
    """
    raw_body = await request.body()

    # ── Signature verification ─────────────────────────────────────────────
    if x_rasen_signature:
        if not verify_rasen_signature(raw_body, x_rasen_signature):
            logger.warning(f"webhook=signature_invalid delivery={x_rasen_delivery}")
            return Response(content="Invalid signature", status_code=400)
    else:
        logger.debug("webhook=no_signature_header (Rasen may not be sending one yet)")

    # ── Deduplication ──────────────────────────────────────────────────────
    if x_rasen_delivery and _is_duplicate(x_rasen_delivery):
        logger.info(f"webhook=duplicate_skipped delivery={x_rasen_delivery}")
        return {"status": "duplicate"}

    # ── Parse payload ──────────────────────────────────────────────────────
    try:
        payload = await request.json()
    except Exception:
        return Response(content="Invalid JSON", status_code=400)

    event = payload.get("event", x_rasen_event or "")
    call = payload.get("call", {})
    call_id = call.get("id", "unknown")

    logger.info(f"webhook=received event={event} call_id={call_id} delivery={x_rasen_delivery}")

    # ── Dispatch to background ─────────────────────────────────────────────
    if event == "call.completed":
        background_tasks.add_task(_process_call_completed, call)

    elif event == "call.analyzed":
        analysis_block = payload.get("analysis", {})
        background_tasks.add_task(_process_call_analyzed, call, analysis_block)

    else:
        logger.debug(f"webhook=unhandled_event event={event}")

    # Always 2xx fast — Rasen retries on anything else or timeout
    return {"status": "accepted", "event": event, "call_id": call_id}
