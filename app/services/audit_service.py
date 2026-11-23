"""Audit event recording service."""
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.models.audit import AuditEvent


class AuditService:
    @staticmethod
    def record_event(
        db: Session,
        session_id: str,
        actor_type: str,
        actor_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        metadata: Dict[str, Any],
    ) -> AuditEvent:
        event = AuditEvent(
            demo_session_id=session_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()
        return event

