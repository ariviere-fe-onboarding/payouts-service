"""Daily ACH batch. Run once a day after the cutoff: python -m payouts.batch."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from payouts.ach import AchClient, SimulatedAch
from payouts.config import get_config
from payouts.crypto import FieldCipher
from payouts.db import Base, make_engine, make_session_factory
from payouts.models import BankAccount, Payout, PayoutStatus

logger = logging.getLogger(__name__)

CUTOFF_HOUR = 17


def batch_cutoff(now: datetime | None = None) -> datetime:
    """Return the most recent 17:00 cutoff."""
    current = now or datetime.now()
    cutoff = current.replace(hour=CUTOFF_HOUR, minute=0, second=0, microsecond=0)
    if current < cutoff:
        cutoff -= timedelta(days=1)
    return cutoff


def run_batch(
    session: Session, cipher: FieldCipher, ach: AchClient, now: datetime | None = None
) -> int:
    """Submit every scheduled payout created before the cutoff. Returns how many were sent."""
    cutoff = batch_cutoff(now)
    scheduled = session.scalars(
        select(Payout)
        .where(Payout.status == PayoutStatus.SCHEDULED, Payout.created_at < cutoff)
        .order_by(Payout.id)
    ).all()
    for payout in scheduled:
        account = session.get(BankAccount, payout.employee_id)
        if account is None:
            payout.status = PayoutStatus.NEEDS_BANK_ACCOUNT
            continue
        payout.ach_trace_id = ach.submit_credit(
            cipher.decrypt(account.routing_number_encrypted),
            cipher.decrypt(account.account_number_encrypted),
            payout.amount_cents,
        )
        payout.status = PayoutStatus.SUBMITTED
    session.commit()
    logger.info("batch before %s submitted %d payouts", cutoff.isoformat(), len(scheduled))
    return len(scheduled)


def main() -> None:
    """Run today's batch against the configured database."""
    config = get_config()
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        sent = run_batch(session, FieldCipher(config.encryption_key), SimulatedAch())
    engine.dispose()
    print(f"Submitted {sent} payouts.")


if __name__ == "__main__":
    main()
