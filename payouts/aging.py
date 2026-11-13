"""Report reimbursements waiting for employee bank details so Finance can follow up."""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, time

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from payouts.config import get_config
from payouts.db import make_engine, make_session_factory
from payouts.models import Payout, PayoutStatus


class AgingQuery(BaseModel):
    """UTC reporting date and inclusive minimum age for outstanding reimbursements."""

    model_config = ConfigDict(frozen=True)

    as_of: date
    min_age_days: int = Field(default=7, ge=0, le=3650)


class EmployeeHold(BaseModel):
    """One employee's reimbursements that qualify for Finance follow-up."""

    employee_id: str
    currency: str
    payout_count: int
    total_cents: int
    oldest_age_days: int
    expense_ids: list[int]


class AgingReport(BaseModel):
    """Read-only snapshot of currently held payouts, grouped by employee and currency."""

    as_of: date
    min_age_days: int
    employees: list[EmployeeHold]


def build_aging_report(session: Session, query: AgingQuery) -> AgingReport:
    """Group qualifying held payouts, ordered by the longest outstanding wait."""
    cutoff = datetime.combine(query.as_of, time.max, tzinfo=UTC)
    payouts = session.scalars(
        select(Payout)
        .where(
            Payout.status == PayoutStatus.NEEDS_BANK_ACCOUNT,
            Payout.created_at <= cutoff,
        )
        .order_by(Payout.expense_id)
    )
    grouped: dict[tuple[str, str], EmployeeHold] = {}
    for payout in payouts:
        created_at = payout.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age_days = (query.as_of - created_at.astimezone(UTC).date()).days
        if age_days < query.min_age_days:
            continue
        key = (payout.employee_id, payout.currency)
        if key not in grouped:
            grouped[key] = EmployeeHold(
                employee_id=payout.employee_id,
                currency=payout.currency,
                payout_count=0,
                total_cents=0,
                oldest_age_days=age_days,
                expense_ids=[],
            )
        employee = grouped[key]
        employee.payout_count += 1
        employee.total_cents += payout.amount_cents
        employee.oldest_age_days = max(employee.oldest_age_days, age_days)
        employee.expense_ids.append(payout.expense_id)
    return AgingReport(
        as_of=query.as_of,
        min_age_days=query.min_age_days,
        employees=sorted(
            grouped.values(),
            key=lambda employee: (
                -employee.oldest_age_days,
                employee.employee_id,
                employee.currency,
            ),
        ),
    )


def main(argv: list[str] | None = None) -> None:
    """Print a JSON report from the configured payouts database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="UTC reporting date, YYYY-MM-DD")
    parser.add_argument(
        "--min-age-days", type=int, default=7, help="Minimum age in days (inclusive)"
    )
    args = parser.parse_args(argv)
    try:
        query = AgingQuery(as_of=args.as_of, min_age_days=args.min_age_days)
    except ValueError as error:
        parser.error(str(error))
    config = get_config()
    engine = make_engine(config.database_url)
    try:
        with make_session_factory(engine)() as session:
            report = build_aging_report(session, query)
        print(report.model_dump_json(indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
