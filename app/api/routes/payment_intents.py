"""Payment intent lifecycle, quote generation, approval, and execution endpoints."""
import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.security import TokenPayload, require_agent_or_user_scope, require_user_scope
from app.database.session import get_db
from app.schemas.payment import (
    PaymentApprovalRequest,
    PaymentExecuteRequest,
    PaymentIntentCreate,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payment-intents", tags=["Payment Intents & Execution"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")


@router.post("", summary="Create a new payment intent draft (DRAFT state)")
def create_payment_intent(
    req: PaymentIntentCreate,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    actor_type = "AGENT" if payload.scope == "agent" else "USER"
    res = PaymentService.create_intent(
        db, payload.session_id, payload.user_id, req, actor_type=actor_type
    )
    return {"success": True, "data": res, "request_id": _req_id(request)}


@router.get("/{intent_id}", summary="Get payment intent details, quotes, and approval snapshot")
def get_payment_intent(
    intent_id: str,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    res = PaymentService.get_intent_by_id(db, payload.session_id, intent_id)
    return {"success": True, "data": res, "request_id": _req_id(request)}


@router.post("/{intent_id}/quotes", summary="Calculate and retrieve ranked payment quotes (QUOTED state)")
def generate_payment_quotes(
    intent_id: str,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    actor_type = "AGENT" if payload.scope == "agent" else "USER"
    res = PaymentService.generate_quotes(
        db, payload.session_id, payload.user_id, intent_id, actor_type=actor_type
    )
    return {"success": True, "data": res, "request_id": _req_id(request)}


@router.post("/{intent_id}/approve", summary="Human-in-the-loop explicit approval of a payment quote (USER ONLY)")
def approve_payment_intent(
    intent_id: str,
    req: PaymentApprovalRequest,
    request: Request,
    payload: TokenPayload = Depends(require_user_scope),  # User only
    db: Session = Depends(get_db),
):
    approval = PaymentService.approve_quote(
        db, payload.session_id, payload.user_id, intent_id, req.quote_id
    )
    return {"success": True, "data": approval, "request_id": _req_id(request)}


@router.post("/{intent_id}/execute", summary="Simulate execution of approved payment (USER ONLY)")
def execute_payment_intent(
    intent_id: str,
    req: PaymentExecuteRequest,
    request: Request,
    payload: TokenPayload = Depends(require_user_scope),  # User only
    db: Session = Depends(get_db),
):
    exec_res = PaymentService.execute_payment(
        db,
        session_id=payload.session_id,
        user_id=payload.user_id,
        intent_id=intent_id,
        idempotency_key=req.idempotency_key,
    )
    return {"success": True, "data": exec_res, "request_id": _req_id(request)}


@router.get("/{intent_id}/status", summary="Check current status of payment intent")
def get_payment_intent_status(
    intent_id: str,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    res = PaymentService.get_intent_by_id(db, payload.session_id, intent_id)
    return {
        "success": True,
        "data": {
            "payment_intent_id": res.id,
            "status": res.status,
            "version": res.version,
            "updated_at": res.updated_at,
        },
        "request_id": _req_id(request),
    }
