"""Offers and rewards endpoints."""
import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.security import TokenPayload, require_agent_or_user_scope
from app.database.session import get_db
from app.services.offer_service import OfferService

router = APIRouter(prefix="/offers", tags=["Offers & Promotions"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")


@router.get("", summary="List simulated promotional offers and reward campaigns")
def list_offers(
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    offers = OfferService.get_offers(db, payload.session_id, active_only=False)
    return {"success": True, "data": offers, "request_id": _req_id(request)}


@router.get("/{offer_id}", summary="Get details of a specific promotional offer")
def get_offer(
    offer_id: str,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    offer = OfferService.get_offer_by_id(db, payload.session_id, offer_id)
    return {"success": True, "data": offer, "request_id": _req_id(request)}

