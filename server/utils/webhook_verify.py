"""
HMAC-SHA256 signature verification for Rasen webhooks.

Rasen signs every webhook request with:
  X-Rasen-Signature: t=<timestamp>,v1=<hex_hmac>

Where:
  HMAC = SHA256( RASEN_WEBHOOK_SECRET, f"{timestamp}.{raw_body_bytes}" )

Replay protection: reject if |now - timestamp| > TOLERANCE_SECONDS.
If RASEN_WEBHOOK_SECRET is not set → skip verification (dev mode, logs warning).
"""

import hashlib
import hmac
import time

from loguru import logger

from server.core.config import RASEN_WEBHOOK_SECRET

TOLERANCE_SECONDS = 300  # 5 minutes


def verify_rasen_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Return True if the signature is valid (or secret not configured).
    Return False if the signature is invalid or the request is a replay.
    """
    if not RASEN_WEBHOOK_SECRET:
        logger.warning(
            "webhook=signature_skipped reason=RASEN_WEBHOOK_SECRET_not_set "
            "(dev mode — set the env var in production)"
        )
        return True  # Allow through in dev

    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        timestamp = parts.get("t", "")
        v1_sig = parts.get("v1", "")
    except Exception:
        logger.warning("webhook=signature_parse_failed header={!r}", signature_header)
        return False

    # Replay check
    try:
        ts_int = int(timestamp)
    except ValueError:
        return False

    if abs(time.time() - ts_int) > TOLERANCE_SECONDS:
        logger.warning(f"webhook=replay_rejected timestamp={timestamp}")
        return False

    # Compute expected signature
    expected = hmac.new(
        RASEN_WEBHOOK_SECRET.encode(),
        f"{timestamp}.".encode() + raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, v1_sig)
