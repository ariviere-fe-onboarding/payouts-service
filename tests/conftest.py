from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from payouts.config import Config
from payouts.crypto import FieldCipher
from payouts.main import create_app
from payouts.seed import seed
from payouts.signing import SIGNATURE_HEADER, compute_signature

CONTRACT_FIXTURE = Path(__file__).parent / "contract" / "expense_approved_v1.json"


class RecordingAch:
    """ACH test double that records every credit."""

    def __init__(self) -> None:
        self.credits: list[tuple[str, str, int]] = []

    def submit_credit(self, routing_number: str, account_number: str, amount_cents: int) -> str:
        self.credits.append((routing_number, account_number, amount_cents))
        return f"TRACE{len(self.credits)}"


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        database_url=f"sqlite:///{tmp_path / 'payouts.sqlite'}",
        webhook_secret="w" * 40,
        service_token="s" * 40,
        encryption_key=Fernet.generate_key().decode("ascii"),
    )


@pytest.fixture
def ach() -> RecordingAch:
    return RecordingAch()


@pytest.fixture
def client(config: Config, ach: RecordingAch) -> Iterator[TestClient]:
    app = create_app(config, ach)
    with app.state.session_factory() as session:
        seed(session, FieldCipher(config.encryption_key))
    with TestClient(app) as test_client:
        yield test_client


def contract_event(**data_overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))
    event["data"].update(data_overrides)
    return event


def signed_headers(secret: str, body: bytes, timestamp: int | None = None) -> dict[str, str]:
    ts = int(time.time()) if timestamp is None else timestamp
    return {
        SIGNATURE_HEADER: f"t={ts},v1={compute_signature(secret, ts, body)}",
        "content-type": "application/json",
    }
