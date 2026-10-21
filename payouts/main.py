"""FastAPI application factory."""

from __future__ import annotations

import hmac
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from payouts import signing
from payouts.ach import AchClient, SimulatedAch
from payouts.config import Config, get_config
from payouts.crypto import FieldCipher
from payouts.db import Base, make_engine, make_session_factory, session_scope
from payouts.models import BankAccount, Payout
from payouts.schemas import BankAccountOut, ExpenseApprovedEvent, PayoutOut
from payouts.service import create_payout

logger = logging.getLogger(__name__)


def app_config(request: Request) -> Config:
    """Return the configuration the running app was built with."""
    config: Config = request.app.state.config
    return config


def db(request: Request) -> Iterator[Session]:
    """Yield a request-scoped database session."""
    yield from session_scope(request.app.state.session_factory)


def require_service_token(
    config: Annotated[Config, Depends(app_config)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Allow only callers presenting the shared service token (expense-app)."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token, config.service_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service token.")


DbSession = Annotated[Session, Depends(db)]
AppConfig = Annotated[Config, Depends(app_config)]


async def expense_approved(request: Request, session: DbSession, config: AppConfig) -> JSONResponse:
    """Receive a signed `expense.approved` webhook and create its payout once."""
    body = await request.body()
    try:
        signing.verify(
            config.webhook_secret,
            request.headers.get(signing.SIGNATURE_HEADER),
            body,
            config.signature_tolerance_seconds,
        )
    except signing.SignatureError as error:
        logger.warning("rejected webhook: %s", error)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature.") from error
    try:
        event = ExpenseApprovedEvent.model_validate_json(body)
    except ValidationError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Payload does not match contract v1."
        ) from error
    payout, created = create_payout(session, event, request.app.state.cipher, request.app.state.ach)
    return JSONResponse(
        {"payout_id": payout.id, "status": payout.status.value},
        status_code=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
    )


def payout_for_expense(expense_id: int, session: DbSession) -> PayoutOut:
    """Return the payout status for one expense."""
    payout = session.scalars(select(Payout).where(Payout.expense_id == expense_id)).first()
    if payout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No payout for this expense.")
    return PayoutOut(
        payout_id=payout.id,
        expense_id=payout.expense_id,
        status=payout.status.value,
        amount_cents=payout.amount_cents,
        currency=payout.currency,
        created_at=payout.created_at,
    )


def bank_account(employee_id: str, session: DbSession) -> BankAccountOut:
    """Return an employee's masked reimbursement destination."""
    account = session.get(BankAccount, employee_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bank account on file.")
    return BankAccountOut(
        employee_id=account.employee_id,
        bank_name=account.bank_name,
        account_last4=account.account_last4,
    )


def healthz() -> dict[str, str]:
    """Liveness probe. The only public route."""
    return {"status": "ok"}


def create_app(config: Config | None = None, ach: AchClient | None = None) -> FastAPI:
    """Build the payouts API. Tests pass their own config and ACH client."""
    cfg = config or get_config()
    engine = make_engine(cfg.database_url)
    Base.metadata.create_all(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="Fernway payouts", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.config = cfg
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.cipher = FieldCipher(cfg.encryption_key)
    app.state.ach = ach or SimulatedAch()

    internal = [Depends(require_service_token)]
    app.add_api_route("/healthz", healthz, methods=["GET"])
    app.add_api_route(
        "/webhooks/expense-approved",
        expense_approved,
        methods=["POST"],
        status_code=status.HTTP_202_ACCEPTED,
    )
    app.add_api_route(
        "/internal/payouts", payout_for_expense, methods=["GET"], dependencies=internal
    )
    app.add_api_route(
        "/internal/employees/{employee_id}/bank-account",
        bank_account,
        methods=["GET"],
        dependencies=internal,
    )
    return app
