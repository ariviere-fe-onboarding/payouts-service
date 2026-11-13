"""Export a bounded queue of held payouts for Finance's bank-account follow-up."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC
from typing import TextIO

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from payouts.config import get_config
from payouts.db import make_engine, make_session_factory
from payouts.models import Payout, PayoutStatus

CSV_COLUMNS = ("payout_id", "expense_id", "employee_id", "amount_cents", "currency", "created_at")


class FollowupOptions(BaseModel):
    """Validated batch size for Finance's oldest-first follow-up queue."""

    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=25, ge=1, le=100)


def export_followups(session: Session, options: FollowupOptions, output: TextIO) -> int:
    """Write the oldest held payouts first, capped at the requested batch size."""
    payouts = session.scalars(
        select(Payout)
        .where(Payout.status == PayoutStatus.NEEDS_BANK_ACCOUNT)
        .order_by(Payout.created_at.asc(), Payout.id)
        .limit(options.limit)
    )
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    count = 0
    for payout in payouts:
        created_at = payout.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        writer.writerow(
            (
                payout.id,
                payout.expense_id,
                payout.employee_id,
                payout.amount_cents,
                payout.currency,
                created_at.astimezone(UTC).isoformat(),
            )
        )
        count += 1
    return count


def main(argv: list[str] | None = None) -> None:
    """Write the oldest pending bank-account follow-ups to stdout as CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=25, help="Batch size, 1-100 (default: 25)")
    args = parser.parse_args(argv)
    try:
        options = FollowupOptions(limit=args.limit)
    except ValueError as error:
        parser.error(str(error))
    config = get_config()
    engine = make_engine(config.database_url)
    try:
        with make_session_factory(engine)() as session:
            count = export_followups(session, options, sys.stdout)
        print(f"Exported {count} follow-ups.", file=sys.stderr)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
