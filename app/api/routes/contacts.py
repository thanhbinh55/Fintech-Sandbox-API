"""Contact searching and management endpoints."""
import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.security import TokenPayload, require_agent_or_user_scope, require_user_scope
from app.database.session import get_db
from app.schemas.contact import ContactCreate
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["Contacts & Recipient Resolution"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")


@router.get("", summary="Search contacts by query string (checks display name, alias, and phone)")
def search_contacts(
    request: Request,
    q: str = Query(..., description="Recipient search string, e.g. 'Minh', '0912345678'"),
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    result = ContactService.search_contacts(db, payload.session_id, payload.user_id, q)
    return {"success": True, "data": result, "request_id": _req_id(request)}


@router.get("/{contact_id}", summary="Get contact details by ID")
def get_contact(
    contact_id: str,
    request: Request,
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    contact = ContactService.get_contact_by_id(db, payload.session_id, payload.user_id, contact_id)
    return {"success": True, "data": contact, "request_id": _req_id(request)}


@router.post("", summary="Create a new contact (User only)")
def create_contact(
    req: ContactCreate,
    request: Request,
    payload: TokenPayload = Depends(require_user_scope),
    db: Session = Depends(get_db),
):
    contact = ContactService.create_contact(db, payload.session_id, payload.user_id, req)
    return {"success": True, "data": contact, "request_id": _req_id(request)}

