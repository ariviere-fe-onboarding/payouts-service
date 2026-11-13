from __future__ import annotations

import json

from fastapi.testclient import TestClient

from payouts.config import Config
from tests.conftest import contract_event, signed_headers


def auth(config: Config) -> dict[str, str]:
    return {"authorization": f"Bearer {config.service_token}"}


def test_internal_routes_require_service_token(client: TestClient) -> None:
    assert client.get("/internal/payouts", params={"expense_id": 42}).status_code == 401
    wrong = {"authorization": "Bearer " + "x" * 40}
    assert (
        client.get("/internal/employees/emp-priya/bank-account", headers=wrong).status_code == 401
    )


def test_payout_lookup(client: TestClient, config: Config) -> None:
    body = json.dumps(contract_event()).encode("utf-8")
    client.post(
        "/webhooks/expense-approved",
        content=body,
        headers=signed_headers(config.webhook_secret, body),
    )
    response = client.get("/internal/payouts", params={"expense_id": 42}, headers=auth(config))
    assert response.status_code == 200
    assert response.json()["amount_cents"] == 18450
    assert response.json()["status"] == "scheduled"


def test_missing_payout_is_404(client: TestClient, config: Config) -> None:
    response = client.get("/internal/payouts", params={"expense_id": 999}, headers=auth(config))
    assert response.status_code == 404


def test_bank_account_is_masked(client: TestClient, config: Config) -> None:
    response = client.get("/internal/employees/emp-priya/bank-account", headers=auth(config))
    assert response.status_code == 200
    assert response.json() == {
        "employee_id": "emp-priya",
        "bank_name": "Harbor Credit Union",
        "account_last4": "6789",
    }
    assert "000123456789" not in response.text
    assert "110000000" not in response.text


def test_missing_bank_account_is_404(client: TestClient, config: Config) -> None:
    response = client.get("/internal/employees/emp-nobody/bank-account", headers=auth(config))
    assert response.status_code == 404


def test_healthz_is_public(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
