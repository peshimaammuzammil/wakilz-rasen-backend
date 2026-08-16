"""
Central configuration — reads from environment variables.
All values have sensible defaults for local dev, but are required for production.
"""

import os
from dotenv import load_dotenv
from loguru import logger

# Load .env file for local development (no-op in production where env vars are set directly)
load_dotenv()

# ── Rasen.ai ──────────────────────────────────────────────────────────────────
RASEN_API_BASE: str = os.getenv(
    "RASEN_API_BASE",
    "https://kalpa-api-454269687527.asia-south1.run.app/api/rasen/workspace",
)
RASEN_API_KEY: str = os.getenv("RASEN_API_KEY", "")
RASEN_AGENT_ID: str = os.getenv("RASEN_AGENT_ID", "")
RASEN_WEBHOOK_SECRET: str = os.getenv("RASEN_WEBHOOK_SECRET", "")  # optional until set

# ── Auth ──────────────────────────────────────────────────────────────────────
JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_SECONDS: int = int(os.getenv("JWT_EXPIRE_SECONDS", "300"))  # 5 min

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGIN: str = os.getenv(
    "ALLOWED_ORIGIN", "https://peshimaammuzammil.github.io"
)

# ── HubSpot ───────────────────────────────────────────────────────────────────
HUBSPOT_ACCESS_TOKEN: str = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
HUBSPOT_API_BASE: str = "https://api.hubapi.com"

# ── Firebase / Firestore ──────────────────────────────────────────────────────
FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "wakilz-dasboard")

# ── Server ────────────────────────────────────────────────────────────────────
PORT: int = int(os.getenv("PORT", "8080"))
MAX_CONCURRENT_SESSIONS: int = int(os.getenv("MAX_CONCURRENT_SESSIONS", "10"))

# ── Session store (in-memory) — replaced by Redis in future ──────────────────
# Imported here so config is the single source; actual dict lives in webrtc.py
SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour


def validate_required() -> list[str]:
    """Return a list of env vars that are required for production but not set."""
    required = {
        "RASEN_API_KEY": RASEN_API_KEY,
        "RASEN_AGENT_ID": RASEN_AGENT_ID,
        "HUBSPOT_ACCESS_TOKEN": HUBSPOT_ACCESS_TOKEN,
        "FIREBASE_PROJECT_ID": FIREBASE_PROJECT_ID,
    }
    missing = [k for k, v in required.items() if not v]
    optional_missing = []
    if not RASEN_WEBHOOK_SECRET:
        optional_missing.append("RASEN_WEBHOOK_SECRET")

    if missing:
        logger.error(f"Missing REQUIRED env vars: {missing}")
    if optional_missing:
        logger.warning(
            f"Missing OPTIONAL env vars (features degraded): {optional_missing}"
        )
    return missing
