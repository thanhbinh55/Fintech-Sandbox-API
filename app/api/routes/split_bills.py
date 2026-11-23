"""Bill splitting and collection endpoints."""
import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.security import TokenPayload, require_agent_or_user_scope, require_user_scope
from app.database.session import get_db
from app.schemas.split import SplitBillCreate, SplitSettleRequest
from app.services.split_service import SplitService

router = APIRouter(prefix="/split-bills", tags=["Bill Splitting"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")


@router.post("", summary="Create an itemized split bill with exact integer calculations")
def create_split_bill(
    req: SplitBillCreate,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    res = SplitService.create_split_bill(db, payload.session_id, payload.user_id, req)
    return {"success": True, "data": res, "request_id": _req_id(request)}


@router.get("/{split_id}", summary="Get split bill details and participant shares")
def get_split_bill(
    split_id: str,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    res = SplitService.get_split_bill(db, payload.session_id, split_id)
    return {"success": True, "data": res, "request_id": _req_id(request)}


@router.get("/{split_id}/status", summary="Get live collection and settlement status of split bill")
def get_split_bill_status(
    split_id: str,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    res = SplitService.get_split_status(db, payload.session_id, split_id)
    return {"success": True, "data": res, "request_id": _req_id(request)}


@router.get("/{split_id}/requests/{request_id}/qr", summary="Get sandbox QR code payload and payment link for a share")
def get_collection_request_qr(
    split_id: str,
    request_id: str,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    bill = SplitService.get_split_bill(db, payload.session_id, split_id)
    col_req = next((cr for cr in bill.collection_requests if cr.request_id == request_id), None)
    if not col_req:
        from app.core.exceptions import ResourceNotFoundException
        raise ResourceNotFoundException("SplitCollectionRequest", request_id)

    is_vietqr = col_req.is_external_payment_rail
    notice = (
        "VIETQR STANDARD DISPLAY QR: Generated per NAPAS EMVCo QR specifications. "
        "This external QR is for mobile banking display and does NOT auto-settle the sandbox ledger."
        if is_vietqr
        else "Sandbox QR payload for internal test payments only. Real banking QR is not generated."
    )

    return {
        "success": True,
        "data": {
            "request_id": col_req.request_id,
            "participant_name": col_req.participant_name,
            "requested_amount_vnd": col_req.requested_amount_vnd,
            "qr_payload": col_req.qr_payload,
            "sandbox_payment_link": col_req.sandbox_payment_link,
            "provider_name": col_req.provider_name,
            "is_external_payment_rail": col_req.is_external_payment_rail,
            "status": col_req.status,
            "simulation_note": notice,
        },
        "request_id": _req_id(request),
    }


@router.post("/{split_id}/requests/{request_id}/settle", summary="Simulate participant paying their share (User action)")
def settle_collection_share(
    split_id: str,
    request_id: str,
    settle_req: SplitSettleRequest,
    request: Request,
    payload: TokenPayload = Depends(require_user_scope),
    db: Session = Depends(get_db),
):
    res = SplitService.settle_collection_request(
        db,
        payload.session_id,
        split_id,
        request_id,
        amount_collected_vnd=settle_req.collected_amount_vnd,
    )
    return {"success": True, "data": res, "request_id": _req_id(request)}

