"""
FastAPI router for Rasen Outbound Voice Calling & Batch Management.

Endpoints:
- GET  /api/rasen/agents              — List available voice agents
- GET  /api/rasen/phone-numbers       — List caller ID phone numbers
- GET  /api/rasen/batch-calls         — List all outbound campaigns
- POST /api/rasen/batch-calls         — Create & launch/schedule a batch call
- GET  /api/rasen/batch-calls/{id}    — Get campaign status and metrics
- GET  /api/rasen/batch-calls/{id}/recipients — Get recipient progress logs
- POST /api/rasen/batch-calls/{id}/cancel — Cancel a batch
- POST /api/rasen/test-call           — Trigger a single test outbound call
- GET  /api/rasen/calls/{id}/recording — Get signed audio recording URL
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from loguru import logger

from server.api.client_auth import decode_client_token
from server.services.rasen_client import get_rasen_client
from server.core.config import RASEN_AGENT_ID

router = APIRouter(prefix="/api/rasen", tags=["rasen-outbound"])


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


# ── Pydantic Request Models ───────────────────────────────────────────────────

class RecipientItem(BaseModel):
    phone_number: str = Field(..., description="E.164 phone number, e.g. +919876543210")
    variables: dict[str, Any] = Field(default_factory=dict, description="Custom prompt variables (name, city, etc.)")
    first_message: str | None = None
    system_prompt: str | None = None
    language: str | None = None
    voice_id: str | None = None


class CreateBatchCallRequest(BaseModel):
    name: str = Field(..., description="Campaign / batch name")
    agent_id: str | None = Field(default=None, description="Agent ID, defaults to workspace real estate agent")
    phone_number_id: str | None = Field(default=None, description="Caller ID phone number ID")
    ringing_timeout: int = Field(default=60, ge=10, le=120, description="Ringing timeout in seconds")
    concurrency_limit: int | None = Field(default=None, ge=1, le=100, description="Concurrent call limit")
    scheduled_at: str | None = Field(default=None, description="ISO timestamp for future execution, or null for immediate")
    recipients: list[RecipientItem] = Field(..., min_length=1, description="List of recipient phone numbers & variables")


class TestCallRequest(BaseModel):
    phone_number: str = Field(..., description="E.164 phone number to test")
    agent_id: str | None = None
    phone_number_id: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/agents")
async def get_agents(
    request: Request,
) -> list[dict[str, Any]]:
    """List agents in the workspace."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        return await client.list_agents()
    except Exception as e:
        logger.error(f"rasen_outbound=list_agents_failed error={e}")
        # Fallback to known agent
        return [{"id": RASEN_AGENT_ID, "name": "Real estate agent"}]


@router.get("/phone-numbers")
async def get_phone_numbers(
    request: Request,
) -> list[dict[str, Any]]:
    """List caller ID phone numbers in the workspace."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        return await client.list_phone_numbers()
    except Exception as e:
        logger.error(f"rasen_outbound=list_phone_numbers_failed error={e}")
        return []


@router.get("/batch-calls")
async def list_batch_campaigns(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List batch campaigns."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        return await client.list_batch_calls(limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"rasen_outbound=list_batch_calls_failed error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-calls")
async def create_batch_campaign(
    request: Request,
    payload: CreateBatchCallRequest,
) -> dict[str, Any]:
    """Create and trigger/schedule a batch outbound campaign."""
    _require_client_token(request)
    client = get_rasen_client()
    agent_id = payload.agent_id or RASEN_AGENT_ID

    body: dict[str, Any] = {
        "agent_id": agent_id,
        "name": payload.name,
        "ringing_timeout": payload.ringing_timeout,
        "recipients": [r.model_dump(exclude_none=True) for r in payload.recipients],
    }
    if payload.phone_number_id:
        body["phone_number_id"] = payload.phone_number_id
    if payload.concurrency_limit:
        body["concurrency_limit"] = payload.concurrency_limit
    if payload.scheduled_at:
        body["scheduled_at"] = payload.scheduled_at

    logger.info(f"rasen_outbound=create_batch name='{payload.name}' recipients={len(payload.recipients)}")

    try:
        return await client.create_batch_call(body)
    except Exception as e:
        logger.error(f"rasen_outbound=create_batch_failed error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch-calls/{batch_id}")
async def get_batch_campaign_details(
    batch_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get campaign details and live calling progress."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        return await client.get_batch_call(batch_id)
    except Exception as e:
        logger.error(f"rasen_outbound=get_batch_failed id={batch_id} error={e}")
        raise HTTPException(status_code=404, detail="Batch campaign not found")


@router.get("/batch-calls/{batch_id}/recipients")
async def get_batch_recipient_logs(
    batch_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get individual recipient logs for a batch."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        return await client.get_batch_recipients(batch_id)
    except Exception as e:
        logger.error(f"rasen_outbound=get_recipients_failed id={batch_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-calls/{batch_id}/cancel")
async def cancel_batch_campaign(
    batch_id: str,
    request: Request,
) -> dict[str, Any]:
    """Cancel a running or scheduled batch."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        return await client.cancel_batch_call(batch_id)
    except Exception as e:
        logger.error(f"rasen_outbound=cancel_batch_failed id={batch_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-call")
async def trigger_test_call(
    request: Request,
    payload: TestCallRequest,
) -> dict[str, Any]:
    """Trigger a single instant test outbound call."""
    _require_client_token(request)
    client = get_rasen_client()
    agent_id = payload.agent_id or RASEN_AGENT_ID

    logger.info(f"rasen_outbound=trigger_test_call to={payload.phone_number} agent={agent_id}")
    try:
        return await client.create_single_call(
            agent_id=agent_id,
            to=payload.phone_number,
            from_number_id=payload.phone_number_id,
            variables=payload.variables,
        )
    except Exception as e:
        logger.error(f"rasen_outbound=test_call_failed error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calls/{call_id}")
async def get_call_details(
    call_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get live call details and status."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        call = await client.get_call(call_id)
        return call
    except Exception as e:
        logger.error(f"rasen_outbound=get_call_failed id={call_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calls/{call_id}/analysis")
async def get_call_live_analysis(
    call_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get live call analysis, transcript turns, and extracted fields."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        return await client.get_call_analysis_raw(call_id)
    except Exception as e:
        logger.error(f"rasen_outbound=get_analysis_failed id={call_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calls/{call_id}/hangup")
async def hangup_live_call(
    call_id: str,
    request: Request,
) -> dict[str, Any]:
    """Terminate an active call."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        await client.hangup_call(call_id)
        return {"status": "hangup_sent", "call_id": call_id}
    except Exception as e:
        logger.error(f"rasen_outbound=hangup_failed id={call_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calls/{call_id}/recording")
async def get_call_recording(
    call_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get fresh signed recording URL for a call."""
    _require_client_token(request)
    client = get_rasen_client()
    try:
        url = await client.get_call_recording_url(call_id)
        if not url:
            raise HTTPException(status_code=404, detail="Recording not available for this call")
        return {"url": url, "call_id": call_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"rasen_outbound=recording_failed id={call_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calls/{call_id}/transcript")
async def get_live_call_transcript(
    call_id: str,
    request: Request,
    after_id: int = Query(0, description="Cursor — return items with id > after_id"),
    limit: int = Query(200, description="Max events to inspect per page"),
) -> dict[str, Any]:
    """
    Poll live transcript utterances for an active (or recently ended) call.

    Proxies to the Rasen Workspace API:
      GET /calls/{call_id}/transcript?after_id=<cursor>&limit=<n>

    Response shape:
      {
        "call_id": "...",
        "status": "in_progress" | "ended" | ...,
        "items": [{ "id", "role": "user"|"assistant", "text", "is_final", ... }],
        "next_after_id": <int>,
        "stream_complete": <bool>
      }

    Keep polling with next_after_id until stream_complete is true.
    """
    _require_client_token(request)
    client = get_rasen_client()
    try:
        data = await client.get_live_transcript(call_id, after_id=after_id, limit=limit)
        return data
    except Exception as e:
        logger.error(f"rasen_outbound=live_transcript_failed id={call_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))

