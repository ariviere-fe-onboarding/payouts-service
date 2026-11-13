"""Coverage for Finance's held-payout follow-up report."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from payouts.aging import AgingQuery, build_aging_report, main
from payouts.config import Config
from payouts.db import Base, make_engine, make_session_factory
from payouts.models import Payout, PayoutStatus


def test_groups_held_payouts_and_excludes_ineligible_records(config: Config) -> None:
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    held = PayoutStatus.NEEDS_BANK_ACCOUNT
    records = [
        (1, "emp-priya", 1, 18450, held),
        (2, "emp-priya", 5, 1550, held),
        (3, "emp-marcus", 3, 999, held),
        (4, "emp-lena", 12, 500, held),
        (5, "emp-jonah", 1, 800, PayoutStatus.SUBMITTED),
        (6, "emp-dana", 1, 900, PayoutStatus.FAILED),
        (7, "emp-future", 20, 200, held),
    ]
    with make_session_factory(engine)() as session:
        for expense_id, employee_id, day, amount_cents, status in records:
            session.add(
                Payout(
                    event_id=f"evt-{expense_id}",
                    expense_id=expense_id,
                    employee_id=employee_id,
                    amount_cents=amount_cents,
                    currency="USD",
                    status=status,
                    created_at=datetime(2026, 11, day, 14, tzinfo=UTC),
                )
            )
        session.commit()
        before = [(p.id, p.status) for p in session.scalars(select(Payout).order_by(Payout.id))]
        report = build_aging_report(session, AgingQuery(as_of=date(2026, 11, 13)))
        assert report.model_dump(mode="json") == {
            "as_of": "2026-11-13",
            "min_age_days": 7,
            "employees": [
                {
                    "employee_id": "emp-priya",
                    "currency": "USD",
                    "payout_count": 2,
                    "total_cents": 20000,
                    "oldest_age_days": 12,
                    "expense_ids": [1, 2],
                },
                {
                    "employee_id": "emp-marcus",
                    "currency": "USD",
                    "payout_count": 1,
                    "total_cents": 999,
                    "oldest_age_days": 10,
                    "expense_ids": [3],
                },
            ],
        }
        after = [(p.id, p.status) for p in session.scalars(select(Payout).order_by(Payout.id))]
        assert after == before
    engine.dispose()


@pytest.mark.parametrize("age", ["-1", "3651", "abc"])
def test_cli_rejects_invalid_minimum_age(age: str) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--as-of", "2026-11-13", "--min-age-days", age])
    assert error.value.code == 2


def test_cli_rejects_invalid_date() -> None:
    with pytest.raises(SystemExit) as error:
        main(["--as-of", "2026-02-30"])
    assert error.value.code == 2


def test_empty_cli_report_is_valid_json(
    config: Config, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setattr("payouts.aging.get_config", lambda: config)
    main(["--as-of", "2026-11-13", "--min-age-days", "14"])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"as_of": "2026-11-13", "min_age_days": 14, "employees": []}
    assert captured.err == ""


@pytest.mark.parametrize("min_age_days", [7, 0])
def test_minimum_age_is_inclusive(config: Config, min_age_days: int) -> None:
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        for expense_id, day in [(1, 13 - min_age_days), (2, 14 - min_age_days)]:
            session.add(
                Payout(
                    event_id=f"evt-{expense_id}",
                    expense_id=expense_id,
                    employee_id="emp-boundary",
                    amount_cents=100,
                    currency="USD",
                    status=PayoutStatus.NEEDS_BANK_ACCOUNT,
                    created_at=datetime(2026, 11, day, 23, 59, tzinfo=UTC),
                )
            )
        session.commit()
        report = build_aging_report(
            session, AgingQuery(as_of=date(2026, 11, 13), min_age_days=min_age_days)
        )
        assert len(report.employees) == 1
        assert report.employees[0].expense_ids == [1]
        assert report.employees[0].oldest_age_days == min_age_days
    engine.dispose()
