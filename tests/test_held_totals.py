"""Tests for Finance's aggregate high-value held-payout summary."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from payouts.config import Config
from payouts.db import Base, make_engine, make_session_factory
from payouts.held_totals import HeldTotalsOptions, main, summarize_held_payouts
from payouts.models import Payout, PayoutStatus


@pytest.fixture
def session(config: Config) -> Iterator[Session]:
    """Provide an isolated database for aggregate report tests."""
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    try:
        with make_session_factory(engine)() as db:
            yield db
    finally:
        engine.dispose()


def add_payout(
    session: Session,
    expense_id: int,
    amount_cents: int,
    status: PayoutStatus = PayoutStatus.NEEDS_BANK_ACCOUNT,
    currency: str = "USD",
) -> None:
    """Insert a synthetic reimbursement without bank data."""
    session.add(
        Payout(
            event_id=f"evt-total-{expense_id}",
            expense_id=expense_id,
            employee_id="emp-priya",
            amount_cents=amount_cents,
            currency=currency,
            status=status,
        )
    )
    session.commit()


def test_summary_filters_status_currency_and_small_amounts(session: Session) -> None:
    add_payout(session, 101, 50_001)
    add_payout(session, 102, 75_000)
    add_payout(session, 103, 49_999)
    add_payout(session, 104, 80_000, PayoutStatus.SUBMITTED)
    add_payout(session, 105, 90_000, PayoutStatus.FAILED)
    add_payout(session, 106, 60_000, currency="EUR")
    before = [(p.id, p.status) for p in session.scalars(select(Payout).order_by(Payout.id))]

    summary = summarize_held_payouts(session, HeldTotalsOptions())

    assert summary.model_dump() == {
        "currency": "USD",
        "minimum_amount_cents": 50_000,
        "payout_count": 2,
        "total_amount_cents": 125_001,
    }
    assert [(p.id, p.status) for p in session.scalars(select(Payout).order_by(Payout.id))] == before


def test_empty_summary_reports_zeroes(session: Session) -> None:
    summary = summarize_held_payouts(session, HeldTotalsOptions())
    assert summary.payout_count == 0
    assert summary.total_amount_cents == 0


def test_custom_minimum_is_applied(session: Session) -> None:
    add_payout(session, 201, 75_000)
    add_payout(session, 202, 125_000)
    summary = summarize_held_payouts(session, HeldTotalsOptions(minimum_amount_cents=100_000))
    assert summary.minimum_amount_cents == 100_000
    assert summary.payout_count == 1
    assert summary.total_amount_cents == 125_000


@pytest.mark.parametrize("minimum", ["0", "-1", "10000001", "1.5", "not-a-number"])
def test_command_rejects_invalid_minimum(minimum: str) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--minimum-amount-cents", minimum])
    assert error.value.code == 2


def test_command_outputs_only_aggregate_json(
    session: Session,
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    add_payout(session, 301, 75_000)
    monkeypatch.setattr("payouts.held_totals.get_config", lambda: config)
    main([])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "currency": "USD",
        "minimum_amount_cents": 50_000,
        "payout_count": 1,
        "total_amount_cents": 75_000,
    }
    assert captured.err == ""
