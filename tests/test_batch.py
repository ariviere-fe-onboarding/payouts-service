from __future__ import annotations

import json
from datetime import datetime

from fastapi.testclient import TestClient

from payouts.batch import batch_cutoff, run_batch
from payouts.config import Config
from payouts.models import Payout
from tests.conftest import RecordingAch, contract_event, signed_headers


def schedule(client: TestClient, config: Config, **data: object) -> None:
    body = json.dumps(contract_event(**data)).encode("utf-8")
    response = client.post(
        "/webhooks/expense-approved",
        content=body,
        headers=signed_headers(config.webhook_secret, body),
    )
    assert response.status_code == 202


def test_cutoff_is_today_after_five() -> None:
    assert batch_cutoff(datetime(2026, 10, 1, 18, 30)) == datetime(2026, 10, 1, 17, 0)


def test_cutoff_is_yesterday_before_five() -> None:
    assert batch_cutoff(datetime(2026, 10, 1, 9, 0)) == datetime(2026, 9, 30, 17, 0)


def test_batch_submits_scheduled_payouts(
    client: TestClient, config: Config, ach: RecordingAch
) -> None:
    schedule(client, config)
    factory = client.app.state.session_factory  # type: ignore[attr-defined]
    cipher = client.app.state.cipher  # type: ignore[attr-defined]
    with factory() as session:
        assert run_batch(session, cipher, ach, now=datetime(2999, 1, 1, 18, 0)) == 1
        payout = session.query(Payout).one()
        assert payout.status.value == "submitted"
        assert payout.ach_trace_id == "TRACE1"
    assert ach.credits == [("110000000", "000123456789", 18450)]


def test_batch_skips_already_submitted(
    client: TestClient, config: Config, ach: RecordingAch
) -> None:
    schedule(client, config)
    factory = client.app.state.session_factory  # type: ignore[attr-defined]
    cipher = client.app.state.cipher  # type: ignore[attr-defined]
    with factory() as session:
        run_batch(session, cipher, ach, now=datetime(2999, 1, 1, 18, 0))
        assert run_batch(session, cipher, ach, now=datetime(2999, 1, 1, 18, 0)) == 0
    assert len(ach.credits) == 1


def test_payout_after_cutoff_waits(client: TestClient, config: Config, ach: RecordingAch) -> None:
    schedule(client, config)
    factory = client.app.state.session_factory  # type: ignore[attr-defined]
    cipher = client.app.state.cipher  # type: ignore[attr-defined]
    with factory() as session:
        assert run_batch(session, cipher, ach, now=datetime(2000, 1, 1, 18, 0)) == 0
    assert ach.credits == []
