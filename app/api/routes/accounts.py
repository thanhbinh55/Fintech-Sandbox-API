"""User accounts and payment sources endpoints."""
import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.security import TokenPayload, require_agent_or_user_scope
from app.database.session import get_db
from app.services.account_service import AccountService

router = APIRouter(tags=["Accounts & Sources"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")


@router.get("/me/accounts", summary="Get all accounts belonging to the primary demo user")
def get_my_accounts(
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    accounts = AccountService.get_user_accounts(db, payload.session_id, payload.user_id)
    return {"success": True, "data": accounts, "request_id": _req_id(request)}


@router.get("/payment-sources", summary="Get candidate payment sources for routing and payment")
def get_payment_sources(
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    sources = AccountService.get_payment_sources(db, payload.session_id, payload.user_id)
    return {"success": True, "data": sources, "request_id": _req_id(request)}


@router.get("/payment-sources/{source_id}", summary="Get specific payment source details")
def get_payment_source_details(
    source_id: str,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    source = AccountService.get_payment_source_by_id(db, payload.session_id, payload.user_id, source_id)
    return {"success": True, "data": source, "request_id": _req_id(request)}
