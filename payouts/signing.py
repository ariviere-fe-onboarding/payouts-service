"""Webhook signature verification (see docs/webhook-contract.md)."""

from __future__ import annotations

import hashlib
import hmac
import time

SIGNATURE_HEADER = "X-Fernway-Signature"


class SignatureError(ValueError):
    """Raised when a webhook signature is missing, malformed, stale, or wrong."""


def compute_signature(secret: str, timestamp: int, body: bytes) -> str:
    """Return the hex HMAC-SHA256 of '<timestamp>.<body>'."""
    message = str(timestamp).encode("ascii") + b"." + body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def parse_header(header: str) -> tuple[int, str]:
    """Split a 't=<unix seconds>,v1=<hex>' header into its parts."""
    parts = dict(item.split("=", 1) for item in header.split(",") if "=" in item)
    timestamp, signature = parts.get("t", ""), parts.get("v1", "")
    if not timestamp.isdigit() or not signature:
        raise SignatureError("Malformed signature header.")
    return int(timestamp), signature


def verify(
    secret: str,
    header: str | None,
    body: bytes,
    tolerance_seconds: int,
    now: float | None = None,
) -> None:
    """Raise SignatureError unless the header is a fresh, valid signature of body."""
    if not header:
        raise SignatureError("Missing signature header.")
    timestamp, signature = parse_header(header)
    current = time.time() if now is None else now
    if abs(current - timestamp) > tolerance_seconds:
        raise SignatureError("Signature timestamp is outside the allowed window.")
    expected = compute_signature(secret, timestamp, body)
    if not hmac.compare_digest(expected, signature):
        raise SignatureError("Signature does not match.")
