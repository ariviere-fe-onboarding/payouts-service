# Fernway payouts service

Reimburses employees for approved expenses. Owned by the **Finance Platform** team.

This is the only Fernway service that stores employee bank details, which keeps every
other service outside the scope of financial audits. It runs and deploys separately
from [`expense-app`](https://github.com/ariviere-fe-onboarding/expense-app), which
notifies it when Finance approves an expense.

```text
expense-app ──(signed expense.approved webhook)──▶ payouts-service ──▶ ACH (simulated)
expense-app ◀──(service-token internal API: payout status, masked bank info)──┘
```

Fernway is fictional. All people, accounts, and numbers are synthetic and no money moves.

## Run locally

Requires Python 3.13+.

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# Generate shared local secrets for both services (run once, from expense-app):
../expense-app/scripts/dev-env.sh
.venv/bin/python -m payouts.seed
.venv/bin/uvicorn payouts.main:create_app --factory --port 8001
```

Approved expenses are scheduled and sent in one ACH batch a day. Run the batch after
the 17:00 cutoff with `.venv/bin/python -m payouts.batch`.

## API

| Route | Auth | Purpose |
|---|---|---|
| `GET /healthz` | Public | Liveness |
| `POST /webhooks/expense-approved` | HMAC signature | Create a payout; see [the contract](docs/webhook-contract.md) |
| `GET /internal/payouts?expense_id=` | Service token | Payout status for one expense |
| `GET /internal/employees/{id}/bank-account` | Service token | Masked bank destination (last four only) |

## Layout

- `payouts/config.py`: the only module that reads the environment (`get_config()`).
- `payouts/signing.py`: webhook signature verification.
- `payouts/service.py`: idempotent payout creation.
- `payouts/crypto.py`: field-level encryption for bank numbers at rest.
- `payouts/main.py`: routes and the app factory.

## Checks

```sh
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/bandit -c pyproject.toml -r payouts
.venv/bin/pytest
.venv/bin/pip-audit -r requirements.txt
```
