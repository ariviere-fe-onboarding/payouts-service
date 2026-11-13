"""Coverage for the Finance reconciliation export."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from io import StringIO

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from payouts.config import Config
from payouts.db import Base, make_engine, make_session_factory
from payouts.models import Payout, PayoutStatus
from payouts.reconciliation import ReconciliationWindow, export_reconciliation, main


def test_csv_preserves_cents_trace_ids_and_order(config: Config) -> None:
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        for expense_id, day, amount_cents in [(43, 11, 999), (42, 10, 18450), (44, 1, 300)]:
            session.add(
                Payout(
                    event_id=f"evt-{expense_id}",
                    expense_id=expense_id,
                    employee_id="emp-priya",
                    amount_cents=amount_cents,
                    currency="USD",
                    status=PayoutStatus.SUBMITTED,
                    ach_trace_id=f"TRACE-{expense_id}",
                    created_at=datetime(2026, 11, day, 14, tzinfo=UTC),
                )
            )
        session.commit()
        output = StringIO()
        count = export_reconciliation(
            session,
            ReconciliationWindow(start_date=date(2026, 11, 10), end_date=date(2026, 11, 12)),
            output,
        )
        rows = list(csv.DictReader(StringIO(output.getvalue())))
        assert count == 2
        assert [row["expense_id"] for row in rows] == ["42", "43"]
        assert [row["amount_cents"] for row in rows] == ["18450", "999"]
        assert rows[0]["currency"] == "USD"
        assert rows[0]["ach_trace_id"] == "TRACE-42"
        assert rows[0]["created_at"] == "2026-11-10T14:00:00+00:00"
        assert set(rows[0]) == {
            "payout_id",
            "expense_id",
            "employee_id",
            "amount_cents",
            "currency",
            "ach_trace_id",
            "created_at",
        }
        assert all(p.status == PayoutStatus.SUBMITTED for p in session.scalars(select(Payout)))
    engine.dispose()


def test_empty_export_still_has_headers(config: Config) -> None:
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        output = StringIO()
        assert (
            export_reconciliation(
                session,
                ReconciliationWindow(start_date=date(2026, 11, 10), end_date=date(2026, 11, 12)),
                output,
            )
            == 0
        )
        assert output.getvalue().startswith("payout_id,expense_id,employee_id,amount_cents,")
        assert len(output.getvalue().splitlines()) == 1
    engine.dispose()


def test_reversed_dates_are_rejected() -> None:
    with pytest.raises(ValidationError, match="end_date"):
        ReconciliationWindow(start_date=date(2026, 11, 12), end_date=date(2026, 11, 10))


@pytest.mark.parametrize("start", ["not-a-date", "2026-02-30"])
def test_cli_rejects_invalid_dates(start: str) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--start-date", start, "--end-date", "2026-11-12"])
    assert error.value.code == 2


def test_cli_separates_csv_from_progress(
    config: Config, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setattr("payouts.reconciliation.get_config", lambda: config)
    main(["--start-date", "2026-11-10", "--end-date", "2026-11-12"])
    captured = capsys.readouterr()
    assert captured.out.startswith("payout_id,")
    assert captured.err == "Exported 0 payouts.\n"
