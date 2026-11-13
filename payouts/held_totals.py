"""Summarize high-value reimbursements waiting for employees' bank details."""

from __future__ import annotations

import argparse
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from payouts.config import get_config
from payouts.db import make_engine, make_session_factory
from payouts.models import Payout, PayoutStatus


class HeldTotalsOptions(BaseModel):
    """Inclusive minimum amount, in USD cents, for the Finance summary."""

    model_config = ConfigDict(frozen=True)

    minimum_amount_cents: StrictInt = Field(default=50_000, ge=1, le=10_000_000)


class HeldPayoutTotals(BaseModel):
    """Aggregate totals without employee identifiers or bank details."""

    model_config = ConfigDict(frozen=True)

    currency: Literal["USD"] = "USD"
    minimum_amount_cents: StrictInt = Field(ge=1, le=10_000_000)
    payout_count: StrictInt = Field(ge=0)
    total_amount_cents: StrictInt = Field(ge=0)


def summarize_held_payouts(session: Session, options: HeldTotalsOptions) -> HeldPayoutTotals:
    """Count and sum held USD payouts at or above the inclusive minimum."""
    row = session.execute(
        select(func.count(Payout.id), func.coalesce(func.sum(Payout.amount_cents), 0)).where(
            Payout.status == PayoutStatus.NEEDS_BANK_ACCOUNT,
            Payout.currency == "USD",
            Payout.amount_cents >= options.minimum_amount_cents,
        )
    ).one()
    return HeldPayoutTotals(
        minimum_amount_cents=options.minimum_amount_cents,
        payout_count=row[0],
        total_amount_cents=row[1],
    )


def main(argv: list[str] | None = None) -> None:
    """Print a JSON summary using the payouts service's configured database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--minimum-amount-cents", type=int, default=50_000, help="Inclusive minimum in USD cents"
    )
    args = parser.parse_args(argv)
    try:
        options = HeldTotalsOptions(minimum_amount_cents=args.minimum_amount_cents)
    except ValueError as error:
        parser.error(str(error))
    config = get_config()
    engine = make_engine(config.database_url)
    try:
        with make_session_factory(engine)() as session:
            summary = summarize_held_payouts(session, options)
        print(summary.model_dump_json())
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
