"""Audit events query endpoint."""
import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenPayload, require_demo_control_scope
from app.database.session import get_db
from app.models import AuditEvent
from app.schemas.event import AuditEventResponse

router = APIRouter(prefix="/events", tags=["Audit & Events"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")


@router.get("", summary="Get audit event logs for caller's demo session (Demo-control scope only)")
def get_audit_events(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    payload: TokenPayload = Depends(require_demo_control_scope),
    db: Session = Depends(get_db),
):
    query = (
        select(AuditEvent)
        .where(AuditEvent.demo_session_id == payload.session_id)
        .order_by(AuditEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    events = db.execute(query).scalars().all()

    data = [
        AuditEventResponse(
            id=ev.id,
            actor_type=ev.actor_type,
            actor_id=ev.actor_id,
            event_type=ev.event_type,
            entity_type=ev.entity_type,
            entity_id=ev.entity_id,
            metadata=ev.metadata_json,
            created_at=ev.created_at,
        )
        for ev in events
    ]

    return {"success": True, "data": data, "request_id": _req_id(request)}
