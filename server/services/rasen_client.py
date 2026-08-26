"""
Async HTTP client wrapper for the Rasen.ai Workspace API.

Docs: https://rasen.docs.buildwithfern.com/workspace-api/
API base: https://kalpa-api-454269687527.asia-south1.run.app/api/rasen/workspace
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger

from server.core.config import RASEN_API_BASE, RASEN_API_KEY


# ── Response models (lightweight dataclasses, not Pydantic) ──────────────────

@dataclass
class AgentSession:
    call_id: str
    status: str
    agent_id: str
    direction: str
    websocket_url: str
    media: dict[str, Any]
    created_at: str
    agent_version_no: int | None = None
    expires_at: str | None = None


@dataclass
class CallAnalysis:
    extraction: dict[str, Any] = field(default_factory=dict)
    sentiment: dict[str, Any] = field(default_factory=dict)
    status: str = "unavailable"


# ── Client ────────────────────────────────────────────────────────────────────

class RasenClient:
    """
    Thin async wrapper around the Rasen workspace REST API.
    Uses httpx.AsyncClient — call client.aclose() on shutdown.
    """

    def __init__(self):
        self._http = httpx.AsyncClient(
            base_url=RASEN_API_BASE,
            headers={
                "Authorization": f"Bearer {RASEN_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

    async def aclose(self):
        await self._http.aclose()

    # ── Agent Sessions ────────────────────────────────────────────────────────

    async def create_agent_session(
        self,
        agent_id: str,
        *,
        variables: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        direction: str = "inbound",
        encoding: str = "pcm16",
        sample_rate: int = 8000,
    ) -> AgentSession:
        """
        POST /agent-sessions
        Creates a Rasen agent runtime and returns the bidirectional media WebSocket URL.
        """
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "direction": direction,
            "media": {
                "transport": "binary",
                "encoding": encoding,
                "sample_rate": sample_rate,
            },
        }
        if variables:
            payload["variables"] = variables
        if metadata:
            payload["metadata"] = metadata

        logger.info(f"rasen=create_agent_session agent_id={agent_id}")
        resp = await self._http.post("/agent-sessions", json=payload)
        resp.raise_for_status()
        data = resp.json()

        return AgentSession(
            call_id=data["call_id"],
            status=data["status"],
            agent_id=data["agent_id"],
            direction=data["direction"],
            websocket_url=data["websocket_url"],
            media=data["media"],
            created_at=data["created_at"],
            agent_version_no=data.get("agent_version_no"),
            expires_at=data.get("expires_at"),
        )

    # ── Calls ─────────────────────────────────────────────────────────────────

    async def list_calls(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """
        GET /calls — paginated call list.
        Returns {"items": [...], "total": N, "limit": N, "offset": N}
        """
        params: dict = {"limit": limit, "offset": offset}
        if agent_id:
            params["agent_id"] = agent_id
        if status:
            params["status"] = status
        resp = await self._http.get("/calls", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_call(self, call_id: str) -> dict[str, Any]:
        """GET /calls/{call_id}"""
        resp = await self._http.get(f"/calls/{call_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_call_analysis(self, call_id: str) -> CallAnalysis:
        """
        GET /calls/{call_id}/analysis
        Returns extraction + sentiment once status is 'succeeded'.
        """
        resp = await self._http.get(f"/calls/{call_id}/analysis")
        resp.raise_for_status()
        data = resp.json()

        extraction_block = data.get("extraction", {})
        sentiment_block = data.get("sentiment", {})

        return CallAnalysis(
            extraction=extraction_block.get("data", {}),
            sentiment=sentiment_block,
            status=extraction_block.get("status", "unavailable"),
        )

    async def get_call_analysis_raw(self, call_id: str) -> dict[str, Any]:
        """
        GET /calls/{call_id}/analysis — returns the raw JSON dict.
        Includes transcript, extraction.data, sentiment, turn_count etc.
        """
        resp = await self._http.get(f"/calls/{call_id}/analysis")
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return resp.json()

    async def get_call_recording_url(self, call_id: str) -> str | None:
        """
        GET /calls/{call_id}/recording
        Returns a fresh signed URL for the call recording.
        """
        try:
            resp = await self._http.get(f"/calls/{call_id}/recording")
            resp.raise_for_status()
            return resp.json().get("url")
        except httpx.HTTPStatusError as e:
            logger.warning(f"rasen=recording_url_failed call_id={call_id} status={e.response.status_code}")
            return None

    async def hangup_call(self, call_id: str) -> None:
        """POST /calls/{call_id}/hangup — idempotent."""
        try:
            resp = await self._http.post(f"/calls/{call_id}/hangup")
            resp.raise_for_status()
            logger.info(f"rasen=hangup call_id={call_id}")
        except httpx.HTTPStatusError as e:
            logger.warning(f"rasen=hangup_failed call_id={call_id} status={e.response.status_code}")

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        """GET /agents/{agent_id} — returns agent config including extraction_fields."""
        resp = await self._http.get(f"/agents/{agent_id}")
        resp.raise_for_status()
        return resp.json()

    async def list_agents(self) -> list[dict[str, Any]]:
        """GET /agents — list all agents in the workspace."""
        resp = await self._http.get("/agents")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("items", [])

    async def list_phone_numbers(self) -> list[dict[str, Any]]:
        """GET /phone-numbers — list active outbound/inbound phone numbers."""
        resp = await self._http.get("/phone-numbers")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("items", [])

    # ── Outbound & Batch Calls ────────────────────────────────────────────────

    async def list_batch_calls(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """GET /batch-calls — list all batch calling campaigns."""
        resp = await self._http.get("/batch-calls", params={"limit": limit, "offset": offset})
        resp.raise_for_status()
        return resp.json()

    async def get_batch_call(self, batch_id: str) -> dict[str, Any]:
        """GET /batch-calls/{batch_id} — get batch campaign details & progress."""
        resp = await self._http.get(f"/batch-calls/{batch_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_batch_recipients(self, batch_id: str) -> dict[str, Any]:
        """GET /batch-calls/{batch_id}/recipients — get individual recipient logs."""
        resp = await self._http.get(f"/batch-calls/{batch_id}/recipients")
        resp.raise_for_status()
        return resp.json()

    async def create_batch_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /batch-calls — create and schedule/launch a batch campaign."""
        resp = await self._http.post("/batch-calls", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def cancel_batch_call(self, batch_id: str) -> dict[str, Any]:
        """POST /batch-calls/{batch_id}/cancel — cancel a running or scheduled batch."""
        resp = await self._http.post(f"/batch-calls/{batch_id}/cancel")
        resp.raise_for_status()
        return resp.json()

    async def create_single_call(
        self,
        agent_id: str,
        to: str,
        from_number_id: str | None = None,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        POST /calls — trigger an immediate single outbound call (used for test calling).
        Falls back to creating a 1-recipient batch if /calls direct outbound is orchestrator-delegated.
        """
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "to": to,
        }
        if from_number_id:
            payload["from_number_id"] = from_number_id
        if variables:
            payload["variables"] = variables

        try:
            resp = await self._http.post("/calls", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"rasen=direct_call_fallback error={e} — using single-recipient batch")
            # Fallback: create an instant 1-recipient batch
            batch_payload = {
                "agent_id": agent_id,
                "name": f"Test Call to {to}",
                "recipients": [{"phone_number": to, "variables": variables or {}}],
            }
            if from_number_id:
                batch_payload["phone_number_id"] = from_number_id
            return await self.create_batch_call(batch_payload)


# ── Singleton ─────────────────────────────────────────────────────────────────
# Shared across the app lifecycle via FastAPI lifespan.
_client: RasenClient | None = None


def get_rasen_client() -> RasenClient:
    global _client
    if _client is None:
        _client = RasenClient()
    return _client


async def close_rasen_client():
    global _client
    if _client:
        await _client.aclose()
        _client = None
