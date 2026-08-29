"""
/api/rasen/calls — Client dashboard data sourced directly from Rasen.

Requires a valid client dashboard JWT (issued by /api/client/verify).
Proxies to the Rasen workspace API, fetches call list + analysis in
parallel, and returns normalised metrics-ready data.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger

from server.api.client_auth import decode_client_token
from server.core.config import RASEN_AGENT_ID
from server.services.rasen_client import get_rasen_client

router = APIRouter()


# ── Auth helper ──────────────────────────────────────────────────────────────

def _require_client_token(request: Request) -> dict:
    """Extract and validate the client dashboard JWT from Bearer header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = auth.removeprefix("Bearer ")
    payload = decode_client_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/api/rasen/calls")
async def get_rasen_calls(
    request: Request,
    start_date: str | None = Query(None, description="ISO date, e.g. 2026-01-01"),
    end_date: str | None = Query(None, description="ISO date, e.g. 2026-12-31"),
    include_analysis: bool = Query(True, description="Fetch extraction data for ended calls"),
    max_calls: int = Query(200, le=500, description="Max calls to fetch from Rasen"),
):
    """
    Returns all Rasen calls (+ extraction analysis for ended calls) filtered
    by date range.  The frontend uses this to compute all dashboard metrics.
    """
    _require_client_token(request)

    rasen = get_rasen_client()

    # ── 1. Fetch all calls in pages ──────────────────────────────────────────
    all_calls: list[dict[str, Any]] = []
    offset = 0
    page_size = 100

    while offset < max_calls:
        fetch_n = min(page_size, max_calls - offset)
        try:
            page = await rasen.list_calls(limit=fetch_n, offset=offset, agent_id=RASEN_AGENT_ID)
        except Exception as exc:
            logger.error(f"rasen_calls=fetch_failed offset={offset} err={exc}")
            raise HTTPException(status_code=502, detail="Failed to fetch calls from Rasen")

        items = page.get("items", [])
        all_calls.extend(items)

        if len(items) < fetch_n:
            break  # last page
        offset += fetch_n

    # ── 2. Date filter (Rasen API doesn't have a server-side date range filter)
    if start_date or end_date:
        def _parse(ds: str) -> datetime:
            return datetime.fromisoformat(ds).replace(tzinfo=timezone.utc)

        lo = _parse(start_date) if start_date else datetime.min.replace(tzinfo=timezone.utc)
        hi = _parse(end_date) if end_date else datetime.max.replace(tzinfo=timezone.utc)
        # Make hi inclusive by advancing to end of day
        hi = hi.replace(hour=23, minute=59, second=59)

        def _in_range(call: dict) -> bool:
            raw = call.get("created_at") or call.get("ended_at")
            if not raw:
                return True
            try:
                ts = datetime.fromisoformat(raw.rstrip("Z")).replace(tzinfo=timezone.utc)
                return lo <= ts <= hi
            except ValueError:
                return True

        all_calls = [c for c in all_calls if _in_range(c)]

    logger.info(f"rasen_calls=fetched total={len(all_calls)} include_analysis={include_analysis}")

    # ── 3. Optionally fetch analysis for ended calls in parallel ─────────────
    analysis_map: dict[str, dict] = {}

    if include_analysis:
        ended_ids = [
            c["id"] for c in all_calls
            if c.get("status") == "ended"
        ]

        async def _fetch_one(call_id: str) -> tuple[str, dict]:
            try:
                data = await rasen.get_call_analysis_raw(call_id)
                return call_id, data
            except Exception as exc:
                logger.warning(f"rasen_calls=analysis_failed call_id={call_id} err={exc}")
                return call_id, {}

        if ended_ids:
            results = await asyncio.gather(*[_fetch_one(cid) for cid in ended_ids])
            analysis_map = dict(results)

    # ── 4. Build response ────────────────────────────────────────────────────
    enriched: list[dict[str, Any]] = []
    for call in all_calls:
        cid = call["id"]
        analysis = analysis_map.get(cid, {})
        extraction_data = analysis.get("extraction", {}).get("data", {}) if analysis else {}
        sentiment = analysis.get("sentiment", {})

        enriched.append({
            # Core call fields
            "id": cid,
            "agent_id": call.get("agent_id"),
            "direction": call.get("direction"),
            "purpose": call.get("purpose"),
            "status": call.get("status"),
            "detailed_status": call.get("detailed_status"),
            "provider": call.get("provider"),
            "to_number_last4": call.get("to_number_last4"),
            "duration_ms": call.get("duration_ms"),
            "created_at": call.get("created_at"),
            "started_at": call.get("started_at"),
            "ended_at": call.get("ended_at"),
            "cost_paise": call.get("cost_paise"),
            # Extraction fields (from analysis)
            "extraction": extraction_data,
            # Transcript turns
            "transcript": analysis.get("transcript", []) or call.get("transcript", []),
            "recording_url": call.get("recording_url") or analysis.get("recording_url"),
            # Sentiment summary
            "sentiment_overall": (
                (sentiment.get("overall") or {}).get("overall_sentiment")
                if isinstance(sentiment, dict)
                else None
            ),
            "turn_count": analysis.get("turn_count"),
        })

    return {
        "calls": enriched,
        "total_fetched": len(enriched),
        "has_analysis": include_analysis,
    }
