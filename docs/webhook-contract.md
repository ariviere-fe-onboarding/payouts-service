# `expense.approved` webhook contract

`expense-app` sends this webhook when Finance gives final approval to an expense.
`payouts-service` is the only consumer. The pinned fixture is
[`tests/contract/expense_approved_v1.json`](../tests/contract/expense_approved_v1.json);
`expense-app` keeps an identical copy and both test suites validate against it.

Contract rules come from the organization guideline
[API contracts](https://github.com/ariviere-fe-onboarding/engineering-standards/blob/main/guidelines/api-contracts.md).

## Request

`POST /webhooks/expense-approved`

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `X-Fernway-Signature` | `t=<unix seconds>,v1=<hex HMAC-SHA256>` |

The signature is HMAC-SHA256 over `<t>.<raw body>` using the shared
`PAYOUTS_WEBHOOK_SECRET`. Requests whose timestamp is more than 300 seconds from the
receiver's clock are rejected.

## Body, version 1

| Field | Type | Notes |
|---|---|---|
| `version` | integer | Always `1` |
| `event_id` | string | Idempotency key, unique per delivery attempt chain |
| `type` | string | Always `expense.approved` |
| `occurred_at` | ISO 8601 UTC | Time of final approval |
| `data.expense_id` | integer | Expense primary key in `expense-app` |
| `data.employee_id` | string | Employee to reimburse, e.g. `emp-priya` |
| `data.amount_cents` | integer | Amount in cents, greater than 0 |
| `data.currency` | string | ISO 4217; only `USD` is supported |
| `data.approved_by` | string | Finance approver's employee ID |

Unknown fields are ignored, so producers may add fields within version 1.

## Responses

| Status | Meaning |
|---|---|
| `202` | Payout created (`submitted` or `needs_bank_account`) |
| `200` | Duplicate `event_id` or `expense_id`; the existing payout is returned |
| `401` | Missing, stale, or invalid signature |
| `422` | Body does not match version 1 |

Producers retry on network errors and `5xx` responses with the same `event_id`.
