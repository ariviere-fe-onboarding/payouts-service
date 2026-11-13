from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from payouts.config import Config
from tests.conftest import contract_event, signed_headers


def post(client: TestClient, config: Config, **data: object) -> None:
    body = json.dumps(contract_event(**data)).encode("utf-8")
    client.post(
        "/webhooks/expense-approved",
        content=body,
        headers=signed_headers(config.webhook_secret, body),
    )


def test_submitted_payout_notifies_employee(
    client: TestClient, config: Config, notifications: list[dict[str, Any]]
) -> None:
    post(client, config)
    assert notifications == [
        {
            "template": "payout-submitted",
            "employee_id": "emp-priya",
            "expense_id": 42,
            "amount_cents": 18450,
            "currency": "USD",
        }
    ]


def test_missing_bank_account_notifies_employee(
    client: TestClient, config: Config, notifications: list[dict[str, Any]]
) -> None:
    post(client, config, employee_id="emp-unknown")
    assert notifications[0]["template"] == "payout-needs-bank-account"


def test_retry_does_not_notify_twice(
    client: TestClient, config: Config, notifications: list[dict[str, Any]]
) -> None:
    post(client, config)
    post(client, config)
    assert len(notifications) == 1


def test_notifications_never_include_bank_details(
    client: TestClient, config: Config, notifications: list[dict[str, Any]]
) -> None:
    post(client, config)
    assert "000123456789" not in json.dumps(notifications)
    assert "110000000" not in json.dumps(notifications)
