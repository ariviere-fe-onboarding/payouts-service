"""Payout status emails, sent through the internal notification service."""

from __future__ import annotations

import os

import httpx

from payouts.models import Payout

NOTIFY_URL = os.environ.get("PAYOUTS_NOTIFY_URL", "http://127.0.0.1:8025/notify")

TEMPLATES = {
    "submitted": "payout-submitted",
    "needs_bank_account": "payout-needs-bank-account",
}


def notify_employee(payout: Payout) -> None:
    """Ask the notification service to email the employee about their payout."""
    template = TEMPLATES.get(payout.status.value)
    if template is None:
        return
    response = httpx.post(
        NOTIFY_URL,
        json={
            "template": template,
            "employee_id": payout.employee_id,
            "expense_id": payout.expense_id,
            "amount_cents": payout.amount_cents,
            "currency": payout.currency,
        },
    )
    response.raise_for_status()
