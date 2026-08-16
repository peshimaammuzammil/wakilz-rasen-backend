"""
WebRTC signaling and audio bridge endpoints.

Endpoints (matching the existing useVoiceAgent.ts hook exactly):
  GET  /session                       → short-lived JWT
  POST /start                         → create Rasen agent session, return sessionId
  POST /sessions/{sessionId}/api/offer → WebRTC SDP exchange + start audio bridge
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger
from pydantic import BaseModel

from server.core.config import (
    MAX_CONCURRENT_SESSIONS,
    RASEN_AGENT_ID,
    SESSION_TTL_SECONDS,
)
from server.core.session_auth import verify_session_token
from server.services.audio_bridge import RasenAudioBridge
from server.services.rasen_client import get_rasen_client

router = APIRouter()

# ── In-memory session store ───────────────────────────────────────────────────

@dataclass
class SessionData:
    session_id: str
    call_id: str
    websocket_url: str
    client_id: str
    pc: RTCPeerConnection | None = None
    bridge: RasenAudioBridge | None = None
    created_at: float = field(default_factory=time.time)


_sessions: dict[str, SessionData] = {}


def _cleanup_expired_sessions():
    """Remove sessions older than SESSION_TTL_SECONDS."""
    now = time.time()
    expired = [
        sid for sid, s in _sessions.items()
        if now - s.created_at > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        sess = _sessions.pop(sid, None)
        if sess:
            asyncio.create_task(_teardown_session(sess))


async def _teardown_session(sess: SessionData):
    """Close WebRTC + Rasen WS for a session."""
    try:
        if sess.bridge:
            await sess.bridge.close()
        if sess.pc:
            await sess.pc.close()
    except Exception as e:
        logger.warning(f"webrtc=teardown_error session_id={sess.session_id} error={e!r}")


def get_active_sessions() -> int:
    return len(_sessions)


# ── Auth dependency ───────────────────────────────────────────────────────────

def _require_token(request: Request) -> None:
    """
    Verify Bearer JWT on all signaling endpoints.
    Localhost is bypassed for dev convenience (same as existing backend).
    """
    origin = request.headers.get("origin", "")
    if "localhost" in origin or "127.0.0.1" in origin:
        return  # dev bypass

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = auth_header.split(" ", 1)[1]
    if not verify_session_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired session token")


# ── Pydantic request/response models ─────────────────────────────────────────

class StartRequest(BaseModel):
    transport: str = "webrtc"
    client_id: str = "wakilz_demo"


class OfferRequest(BaseModel):
    sdp: str
    type: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start")
async def start(body: StartRequest, _: None = Depends(_require_token)):
    """
    Called by the browser after GET /session.
    1. Creates a Rasen agent session
    2. Stores call_id + websocket_url in session store
    3. Returns { sessionId } to browser
    """
    _cleanup_expired_sessions()

    if len(_sessions) >= MAX_CONCURRENT_SESSIONS:
        raise HTTPException(
            status_code=503,
            detail=f"Too many concurrent sessions (max {MAX_CONCURRENT_SESSIONS}). Try again shortly.",
        )

    rasen = get_rasen_client()
    try:
        agent_session = await rasen.create_agent_session(
            RASEN_AGENT_ID,
            variables={},
            metadata={"client_id": body.client_id},
            direction="inbound",
        )
    except Exception as e:
        logger.error(f"webrtc=rasen_session_create_failed error={e!r}")
        raise HTTPException(status_code=502, detail=f"Failed to create Rasen session: {e}")

    session_id = str(uuid.uuid4())
    _sessions[session_id] = SessionData(
        session_id=session_id,
        call_id=agent_session.call_id,
        websocket_url=agent_session.websocket_url,
        client_id=body.client_id,
    )

    logger.info(
        f"webrtc=session_created session_id={session_id} "
        f"call_id={agent_session.call_id} client_id={body.client_id}"
    )
    return {"sessionId": session_id}


@router.post("/sessions/{session_id}/api/offer")
async def offer(session_id: str, body: OfferRequest, _: None = Depends(_require_token)):
    """
    Called by the browser with its SDP WebRTC offer.
    1. Creates aiortc RTCPeerConnection
    2. Opens Rasen media WebSocket
    3. Sets up bidirectional audio bridge
    4. Returns SDP answer to browser
    """
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Create WebRTC peer connection
    pc = RTCPeerConnection(configuration={
        "iceServers": [{"urls": "stun:stun.l.google.com:19302"}]
    })
    sess.pc = pc

    # Create Rasen audio bridge and connect to Rasen WS
    bridge = RasenAudioBridge(sess.websocket_url, sess.call_id)
    sess.bridge = bridge

    try:
        await bridge.connect()
    except Exception as e:
        logger.error(f"webrtc=rasen_ws_connect_failed call_id={sess.call_id} error={e!r}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to Rasen WebSocket: {e}")

    # Add Rasen output track to peer connection (Rasen → browser audio)
    output_track = bridge.output_track
    pc.addTrack(output_track)

    # Handle incoming browser audio track → forward to Rasen
    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            logger.info(f"webrtc=browser_track_received call_id={sess.call_id}")
            bridge.start_forwarding(track)

    # Handle peer connection state changes
    @pc.on("connectionstatechange")
    async def on_connection_state_change():
        state = pc.connectionState
        logger.info(f"webrtc=connection_state_change state={state} call_id={sess.call_id}")
        if state in ("disconnected", "failed", "closed"):
            # Tear down bridge and clean up session
            await _teardown_session(sess)
            _sessions.pop(session_id, None)

    # SDP negotiation
    await pc.setRemoteDescription(RTCSessionDescription(sdp=body.sdp, type=body.type))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    logger.info(f"webrtc=offer_answered session_id={session_id} call_id={sess.call_id}")
    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }
