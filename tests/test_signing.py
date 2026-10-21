from __future__ import annotations

import pytest

from payouts.signing import SignatureError, compute_signature, parse_header, verify

SECRET = "k" * 40
BODY = b'{"hello":"world"}'


def header(timestamp: int, body: bytes = BODY, secret: str = SECRET) -> str:
    return f"t={timestamp},v1={compute_signature(secret, timestamp, body)}"


def test_valid_signature_passes() -> None:
    verify(SECRET, header(1_000), BODY, tolerance_seconds=300, now=1_100)


@pytest.mark.parametrize("value", [None, ""])
def test_missing_header_is_rejected(value: str | None) -> None:
    with pytest.raises(SignatureError, match="Missing"):
        verify(SECRET, value, BODY, tolerance_seconds=300, now=1_000)


@pytest.mark.parametrize("value", ["garbage", "t=abc,v1=00", "t=100", "v1=00"])
def test_malformed_header_is_rejected(value: str) -> None:
    with pytest.raises(SignatureError, match="Malformed"):
        parse_header(value)


def test_stale_timestamp_is_rejected() -> None:
    with pytest.raises(SignatureError, match="window"):
        verify(SECRET, header(1_000), BODY, tolerance_seconds=300, now=1_301)


def test_tampered_body_is_rejected() -> None:
    with pytest.raises(SignatureError, match="does not match"):
        verify(SECRET, header(1_000), b'{"hello":"mallory"}', tolerance_seconds=300, now=1_000)


def test_wrong_secret_is_rejected() -> None:
    with pytest.raises(SignatureError, match="does not match"):
        verify(SECRET, header(1_000, secret="x" * 40), BODY, tolerance_seconds=300, now=1_000)
