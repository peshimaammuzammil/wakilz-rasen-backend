"""
FastAPI entry point for the Wakilz Rasen Backend.

Endpoints:
  GET  /session                          → short-lived JWT for browser
  POST /start                            → create Rasen agent session
  POST /sessions/{id}/api/offer          → WebRTC SDP exchange + audio bridge
  POST /webhooks/rasen                   → Rasen call.completed / call.analyzed
  GET  /api/client/verify                → client key → scoped JWT
  GET  /api/conversations                → list conversations (admin/client scoped)
  GET  /api/conversations/{id}           → single conversation
  GET  /api/conversations/{id}/audio     → fresh recording URL from Rasen
  GET  /health                           → uptime + active sessions

Run locally:
  python -m server.core.main

Deploy on Cloud Run:
  Docker container exposes PORT (default 8080).
"""

import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from server.core.config import ALLOWED_ORIGIN, validate_required
from server.core.session_auth import router as session_router
from server.api.webrtc import router as webrtc_router, get_active_sessions
from server.api.webhooks import router as webhooks_router
from server.api.conversations import router as conversations_router
from server.api.client_auth import router as client_auth_router
from server.services.rasen_client import close_rasen_client
from server.services.hubspot import close_hubspot_client
from server.services.firestore_db import seed_demo_client_key


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    # Startup
    logger.info("event=startup")
    missing = validate_required()
    if missing:
        logger.warning(f"event=startup_warnings missing={missing}")

    # Seed the wakilz_demo client key in Firestore (idempotent)
    try:
        await seed_demo_client_key()
    except Exception as e:
        logger.warning(f"event=seed_failed error={e!r} (Firestore may not be reachable locally)")

    yield  # App runs here

    # Shutdown
    logger.info("event=shutdown")
    await close_rasen_client()
    await close_hubspot_client()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Wakilz Rasen Backend",
    version="1.0.0",
    docs_url=None,   # disable public swagger
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(session_router)        # GET /session
app.include_router(webrtc_router)         # POST /start, POST /sessions/{id}/api/offer
app.include_router(webhooks_router)       # POST /webhooks/rasen
app.include_router(conversations_router)  # GET /api/conversations*
app.include_router(client_auth_router)    # GET /api/client/verify


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Cloud Run health check + active session count."""
    return {
        "status": "ok",
        "sessions_active": get_active_sessions(),
        "version": "1.0.0",
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting Wakilz Rasen Backend on port {port}")
    uvicorn.run(
        "server.core.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
