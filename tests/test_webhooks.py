from __future__ import annotations

import json
import time

import httpx
from fastapi.testclient import TestClient

from payouts.config import Config
from tests.conftest import RecordingAch, contract_event, signed_headers

URL = "/webhooks/expense-approved"


def post_event(client: TestClient, config: Config, event: dict[str, object]) -> httpx.Response:
    body = json.dumps(event).encode("utf-8")
    return client.post(URL, content=body, headers=signed_headers(config.webhook_secret, body))


def test_contract_fixture_schedules_payout(
    client: TestClient, config: Config, ach: RecordingAch
) -> None:
    response = post_event(client, config, contract_event())
    assert response.status_code == 202
    assert response.json()["status"] == "scheduled"
    assert ach.credits == []


def test_retried_event_is_paid_once(client: TestClient, config: Config, ach: RecordingAch) -> None:
    first = post_event(client, config, contract_event())
    second = post_event(client, config, contract_event())
    assert second.status_code == 200
    assert second.json() == first.json()


def test_same_expense_with_new_event_id_is_paid_once(
    client: TestClient, config: Config, ach: RecordingAch
) -> None:
    post_event(client, config, contract_event())
    replay = contract_event()
    replay["event_id"] = "evt-different"
    assert post_event(client, config, replay).status_code == 200


def test_employee_without_bank_account_is_held(
    client: TestClient, config: Config, ach: RecordingAch
) -> None:
    response = post_event(client, config, contract_event(employee_id="emp-unknown"))
    assert response.json()["status"] == "needs_bank_account"
    assert ach.credits == []


def test_unsigned_request_is_rejected(client: TestClient, ach: RecordingAch) -> None:
    response = client.post(URL, json=contract_event())
    assert response.status_code == 401
    assert ach.credits == []


def test_bad_signature_is_rejected(client: TestClient, ach: RecordingAch) -> None:
    body = json.dumps(contract_event()).encode("utf-8")
    response = client.post(URL, content=body, headers=signed_headers("z" * 40, body))
    assert response.status_code == 401
    assert ach.credits == []


def test_replayed_old_signature_is_rejected(client: TestClient, config: Config) -> None:
    body = json.dumps(contract_event()).encode("utf-8")
    stale = signed_headers(config.webhook_secret, body, int(time.time()) - 3_600)
    assert client.post(URL, content=body, headers=stale).status_code == 401


def test_float_amount_violates_contract(
    client: TestClient, config: Config, ach: RecordingAch
) -> None:
    response = post_event(client, config, contract_event(amount_cents=184.5))
    assert response.status_code == 422
    assert ach.credits == []


def test_unknown_version_is_rejected(client: TestClient, config: Config) -> None:
    event = contract_event()
    event["version"] = 2
    assert post_event(client, config, event).status_code == 422


def test_unsupported_currency_is_rejected(client: TestClient, config: Config) -> None:
    response = post_event(client, config, contract_event(currency="EUR"))
    assert response.status_code == 422
