"""Payout creation. Each webhook event and each expense is paid at most once."""

from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from payouts.models import BankAccount, Payout, PayoutStatus
from payouts.schemas import ExpenseApprovedEvent

logger = logging.getLogger(__name__)


def existing_payout(session: Session, event: ExpenseApprovedEvent) -> Payout | None:
    """Return the payout already created for this event or expense, if any."""
    return session.scalars(
        select(Payout).where(
            or_(Payout.event_id == event.event_id, Payout.expense_id == event.data.expense_id)
        )
    ).first()


def create_payout(session: Session, event: ExpenseApprovedEvent) -> tuple[Payout, bool]:
    """Schedule the payout for an event in the next daily batch. Returns (payout, created)."""
    if (found := existing_payout(session, event)) is not None:
        return found, False

    data = event.data
    payout = Payout(
        event_id=event.event_id,
        expense_id=data.expense_id,
        employee_id=data.employee_id,
        amount_cents=data.amount_cents,
        currency=data.currency,
        status=PayoutStatus.NEEDS_BANK_ACCOUNT,
    )
    session.add(payout)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        if (found := existing_payout(session, event)) is not None:
            return found, False
        raise

    if session.get(BankAccount, data.employee_id) is not None:
        payout.status = PayoutStatus.SCHEDULED
    session.commit()
    logger.info("payout %s for expense %s: %s", payout.id, payout.expense_id, payout.status)
    return payout, True
