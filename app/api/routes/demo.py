"""Demo session creation, reset, and simulation endpoints."""
import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.core.security import (
    TokenPayload,
    require_any_scope,
    require_demo_control_scope,
    require_user_scope,
)
from app.database.session import get_db
from app.models import Account, Transaction
from app.schemas.session import DemoSessionCreate, DemoSessionResponse
from app.services.audit_service import AuditService
from app.services.demo_service import DemoService
from app.services.ledger_service import LedgerService

router = APIRouter(prefix="/demo", tags=["Demo & Sessions"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")


@router.post("/sessions", summary="Create a new isolated demo session seeded with financial scenario")
def create_demo_session(req: DemoSessionCreate, request: Request, db: Session = Depends(get_db)):
    res = DemoService.create_session(db, req)
    return {"success": True, "data": res, "request_id": _req_id(request)}


@router.get("/sessions/me", summary="Get details of active demo session")
def get_current_session(
    request: Request,
    payload: TokenPayload = Depends(require_any_scope),
    db: Session = Depends(get_db),
):
    res = DemoService.get_session(db, payload.session_id)
    return {"success": True, "data": res, "request_id": _req_id(request)}


@router.post("/reset", summary="Reset caller's demo session to initial seed state")
def reset_demo_session(
    request: Request,
    payload: TokenPayload = Depends(require_any_scope),  # user or demo-control can reset their own session
    db: Session = Depends(get_db),
):
    # Agent is explicitly forbidden from resetting session
    if payload.scope == "agent":
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("AI Agent is forbidden from executing demo session resets.")

    res = DemoService.reset_session(db, payload.session_id)
    return {"success": True, "data": res, "request_id": _req_id(request)}


@router.post("/simulate-incoming", summary="Simulate incoming top-up / deposit (Demo-control only)")
def simulate_incoming_money(
    account_id: str,
    amount_vnd: int,
    request: Request,
    payload: TokenPayload = Depends(require_demo_control_scope),
    db: Session = Depends(get_db),
):
    acc = db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.demo_session_id == payload.session_id,
        )
    ).scalar_one_or_none()

    if not acc:
        raise ResourceNotFoundException("Account", account_id)

    acc.available_balance_vnd += amount_vnd

    AuditService.record_event(
        db=db,
        session_id=payload.session_id,
        actor_type="DEMO_CONTROL",
        actor_id=payload.user_id,
        event_type="SIMULATED_DEPOSIT",
        entity_type="ACCOUNT",
        entity_id=acc.id,
        metadata={"amount_vnd": amount_vnd, "new_balance_vnd": acc.available_balance_vnd},
    )
    db.commit()

    return {
        "success": True,
        "data": {
            "account_id": acc.id,
            "amount_deposited_vnd": amount_vnd,
            "new_available_balance_vnd": acc.available_balance_vnd,
            "message": "Simulated deposit credited successfully.",
        },
        "request_id": _req_id(request),
    }

