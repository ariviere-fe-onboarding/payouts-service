"""Persistence models. Bank account numbers are stored only in encrypted form."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from payouts.db import Base


def utcnow() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class PayoutStatus(StrEnum):
    """Lifecycle of a reimbursement payout."""

    SCHEDULED = "scheduled"
    SUBMITTED = "submitted"
    NEEDS_BANK_ACCOUNT = "needs_bank_account"
    FAILED = "failed"


class BankAccount(Base):
    """An employee's reimbursement destination."""

    __tablename__ = "bank_accounts"

    employee_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bank_name: Mapped[str] = mapped_column(String(100))
    routing_number_encrypted: Mapped[str] = mapped_column(String(500))
    account_number_encrypted: Mapped[str] = mapped_column(String(500))
    account_last4: Mapped[str] = mapped_column(String(4))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Payout(Base):
    """A reimbursement for one approved expense."""

    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    expense_id: Mapped[int] = mapped_column(Integer, unique=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[PayoutStatus] = mapped_column(Enum(PayoutStatus, native_enum=False))
    ach_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
