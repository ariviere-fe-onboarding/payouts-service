"""Request and response schemas. Webhook schemas pin contract version 1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


class ExpenseApprovedData(BaseModel):
    """The approved expense to reimburse."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    expense_id: StrictInt = Field(gt=0)
    employee_id: StrictStr = Field(min_length=1, max_length=64)
    amount_cents: StrictInt = Field(gt=0, le=10_000_000)
    currency: Literal["USD"]
    approved_by: StrictStr = Field(min_length=1, max_length=64)


class ExpenseApprovedEvent(BaseModel):
    """Webhook envelope for `expense.approved`, contract version 1."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    version: Literal[1]
    event_id: StrictStr = Field(min_length=1, max_length=64)
    type: Literal["expense.approved"]
    occurred_at: datetime
    data: ExpenseApprovedData


class PayoutOut(BaseModel):
    """Payout status returned to expense-app."""

    payout_id: int
    expense_id: int
    status: str
    amount_cents: int
    currency: str
    created_at: datetime


class BankAccountOut(BaseModel):
    """Masked bank destination. Full numbers never leave this service."""

    employee_id: str
    bank_name: str
    account_last4: str
