"""Behavior checks for the Finance bank-account follow-up export."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import UTC, datetime
from io import StringIO

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from payouts.config import Config
from payouts.db import Base, make_engine, make_session_factory
from payouts.followups import FollowupOptions, export_followups, main
from payouts.models import Payout, PayoutStatus


@pytest.fixture
def session(config: Config) -> Iterator[Session]:
    """Provide an isolated payouts database for report tests."""
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    try:
        with make_session_factory(engine)() as db:
            yield db
    finally:
        engine.dispose()


def add_payout(session: Session, expense_id: int, status: PayoutStatus) -> Payout:
    """Insert a synthetic reimbursement with a fixed UTC creation time."""
    payout = Payout(
        event_id=f"evt-followup-{expense_id}",
        expense_id=expense_id,
        employee_id="emp-priya",
        amount_cents=18450,
        currency="USD",
        status=status,
        created_at=datetime(2026, 11, 10, 14, tzinfo=UTC),
    )
    session.add(payout)
    session.commit()
    return payout


def test_export_contains_only_held_payouts_and_safe_fields(session: Session) -> None:
    held = add_payout(session, 101, PayoutStatus.NEEDS_BANK_ACCOUNT)
    add_payout(session, 102, PayoutStatus.SUBMITTED)
    add_payout(session, 103, PayoutStatus.FAILED)
    before = [(p.id, p.status) for p in session.scalars(select(Payout).order_by(Payout.id))]
    output = StringIO()

    assert export_followups(session, FollowupOptions(), output) == 1
    assert list(csv.DictReader(StringIO(output.getvalue()))) == [
        {
            "payout_id": str(held.id),
            "expense_id": "101",
            "employee_id": "emp-priya",
            "amount_cents": "18450",
            "currency": "USD",
            "created_at": "2026-11-10T14:00:00+00:00",
        }
    ]
    assert [(p.id, p.status) for p in session.scalars(select(Payout).order_by(Payout.id))] == before


def test_batch_limit_and_stable_ties(session: Session) -> None:
    first = add_payout(session, 201, PayoutStatus.NEEDS_BANK_ACCOUNT)
    add_payout(session, 202, PayoutStatus.NEEDS_BANK_ACCOUNT)
    output = StringIO()

    assert export_followups(session, FollowupOptions(limit=1), output) == 1
    rows = list(csv.DictReader(StringIO(output.getvalue())))
    assert [row["payout_id"] for row in rows] == [str(first.id)]


def test_batch_selects_oldest_before_applying_limit(session: Session) -> None:
    newest = add_payout(session, 211, PayoutStatus.NEEDS_BANK_ACCOUNT)
    oldest = add_payout(session, 212, PayoutStatus.NEEDS_BANK_ACCOUNT)
    middle = add_payout(session, 213, PayoutStatus.NEEDS_BANK_ACCOUNT)
    newest.created_at = datetime(2026, 11, 12, 14, tzinfo=UTC)
    oldest.created_at = datetime(2026, 11, 10, 14, tzinfo=UTC)
    middle.created_at = datetime(2026, 11, 11, 14, tzinfo=UTC)
    session.commit()
    output = StringIO()

    assert export_followups(session, FollowupOptions(limit=2), output) == 2
    rows = list(csv.DictReader(StringIO(output.getvalue())))
    assert [row["payout_id"] for row in rows] == [str(oldest.id), str(middle.id)]


def test_empty_queue_has_headers(session: Session) -> None:
    output = StringIO()
    assert export_followups(session, FollowupOptions(), output) == 0
    assert output.getvalue().splitlines() == [
        "payout_id,expense_id,employee_id,amount_cents,currency,created_at"
    ]


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_invalid_batch_size_is_rejected(limit: int) -> None:
    with pytest.raises(ValidationError):
        FollowupOptions(limit=limit)


@pytest.mark.parametrize("limit", ["0", "101", "not-a-number"])
def test_command_rejects_invalid_batch_size(limit: str) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--limit", limit])
    assert error.value.code == 2


def test_command_separates_csv_from_progress(
    session: Session,
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    add_payout(session, 301, PayoutStatus.NEEDS_BANK_ACCOUNT)
    monkeypatch.setattr("payouts.followups.get_config", lambda: config)
    main(["--limit", "25"])
    captured = capsys.readouterr()
    assert len(list(csv.DictReader(StringIO(captured.out)))) == 1
    assert captured.err == "Exported 1 follow-ups.\n"
