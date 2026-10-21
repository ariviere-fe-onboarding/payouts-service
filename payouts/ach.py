"""ACH submission. The demo uses a simulator; no money moves."""

from __future__ import annotations

import secrets
from typing import Protocol


class AchClient(Protocol):
    """Submits a credit to an employee's bank account and returns a trace ID."""

    def submit_credit(self, routing_number: str, account_number: str, amount_cents: int) -> str:
        """Submit the credit and return the network trace ID."""
        ...


class SimulatedAch:
    """Accepts every credit and returns a random trace ID."""

    def submit_credit(self, routing_number: str, account_number: str, amount_cents: int) -> str:
        """Pretend to submit the credit."""
        return f"ACH{secrets.token_hex(6).upper()}"
