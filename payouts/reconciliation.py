"""Export submitted reimbursements for Finance's bank reconciliation workflow."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, date, datetime, time
from typing import TextIO

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from payouts.config import get_config
from payouts.db import make_engine, make_session_factory
from payouts.models import Payout, PayoutStatus

CSV_COLUMNS = (
    "payout_id",
    "expense_id",
    "employee_id",
    "amount_cents",
    "currency",
    "ach_trace_id",
    "created_at",
)


class ReconciliationWindow(BaseModel):
    """Inclusive UTC calendar dates requested by Finance."""

    model_config = ConfigDict(frozen=True)

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_order(self) -> ReconciliationWindow:
        """Reject reversed date ranges before querying the database."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


def export_reconciliation(session: Session, window: ReconciliationWindow, output: TextIO) -> int:
    """Write submitted payouts in the requested date window; return the row count."""
    start = datetime.combine(window.start_date, time.min, tzinfo=UTC)
    end = datetime.combine(window.end_date, time.max, tzinfo=UTC)
    payouts = session.scalars(
        select(Payout)
        .where(
            Payout.created_at >= start,
            Payout.created_at <= end,
            Payout.status == PayoutStatus.SUBMITTED,
        )
        .order_by(Payout.created_at, Payout.id)
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
                payout.ach_trace_id or "",
                created_at.astimezone(UTC).isoformat(),
            )
        )
        count += 1
    return count


def main(argv: list[str] | None = None) -> None:
    """Write a reconciliation CSV to stdout using the configured payouts database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date", required=True, help="First UTC date, YYYY-MM-DD (inclusive)"
    )
    parser.add_argument("--end-date", required=True, help="Last UTC date, YYYY-MM-DD (inclusive)")
    args = parser.parse_args(argv)
    try:
        window = ReconciliationWindow(start_date=args.start_date, end_date=args.end_date)
    except ValueError as error:
        parser.error(str(error))
    config = get_config()
    engine = make_engine(config.database_url)
    try:
        with make_session_factory(engine)() as session:
            count = export_reconciliation(session, window, sys.stdout)
        print(f"Exported {count} payouts.", file=sys.stderr)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
