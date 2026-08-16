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
