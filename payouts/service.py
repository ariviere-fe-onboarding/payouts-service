"""Payout creation. Each webhook event and each expense is paid at most once."""

from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from payouts.ach import AchClient
from payouts.crypto import FieldCipher
from payouts.models import BankAccount, Payout, PayoutStatus
from payouts.notify import notify_employee
from payouts.schemas import ExpenseApprovedEvent

logger = logging.getLogger(__name__)


def existing_payout(session: Session, event: ExpenseApprovedEvent) -> Payout | None:
    """Return the payout already created for this event or expense, if any."""
    return session.scalars(
        select(Payout).where(
            or_(Payout.event_id == event.event_id, Payout.expense_id == event.data.expense_id)
        )
    ).first()


def create_payout(
    session: Session, event: ExpenseApprovedEvent, cipher: FieldCipher, ach: AchClient
) -> tuple[Payout, bool]:
    """Create and submit the payout for an event. Returns (payout, created)."""
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

    account = session.get(BankAccount, data.employee_id)
    if account is not None:
        payout.ach_trace_id = ach.submit_credit(
            cipher.decrypt(account.routing_number_encrypted),
            cipher.decrypt(account.account_number_encrypted),
            data.amount_cents,
        )
        payout.status = PayoutStatus.SUBMITTED
    session.commit()
    logger.info("payout %s for expense %s: %s", payout.id, payout.expense_id, payout.status)
    notify_employee(payout)
    return payout, True
