"""Demo session lifecycle service."""
from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundException
from app.core.security import generate_session_token
from app.database.seed import seed_demo_data
from app.models import DemoSession, User
from app.schemas.session import DemoSessionCreate, DemoSessionResponse, SessionCredentials


class DemoService:
    @staticmethod
    def create_session(db: Session, request: DemoSessionCreate) -> DemoSessionResponse:
        settings = get_settings()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.SESSION_TOKEN_EXPIRE_HOURS)

        session_id = str(uuid.uuid4())
        display_name = request.display_name or f"Demo Environment ({request.scenario})"

        demo_session = DemoSession(
            id=session_id,
            display_name=display_name,
            owner_id="admin",
            seed_scenario=request.scenario,
            seed_version="1.0.0",
            status="ACTIVE",
            created_at=now,
            expires_at=expires_at,
        )
        db.add(demo_session)
        db.flush()

        # Seed data
        primary_user = seed_demo_data(db, demo_session, scenario=request.scenario)
        db.commit()
        db.refresh(demo_session)

        # Generate scoped tokens
        credentials = SessionCredentials(
            user_token=generate_session_token(demo_session.id, primary_user.id, "user"),
            agent_token=generate_session_token(demo_session.id, primary_user.id, "agent"),
            demo_control_token=generate_session_token(demo_session.id, primary_user.id, "demo-control"),
        )

        return DemoSessionResponse(
            id=demo_session.id,
            display_name=demo_session.display_name,
            seed_scenario=demo_session.seed_scenario,
            seed_version=demo_session.seed_version,
            status=demo_session.status,
            created_at=demo_session.created_at,
            expires_at=demo_session.expires_at,
            credentials=credentials,
        )

    @staticmethod
    def get_session(db: Session, session_id: str) -> DemoSessionResponse:
        session = db.get(DemoSession, session_id)
        if not session:
            raise ResourceNotFoundException("DemoSession", session_id)

        return DemoSessionResponse(
            id=session.id,
            display_name=session.display_name,
            seed_scenario=session.seed_scenario,
            seed_version=session.seed_version,
            status=session.status,
            created_at=session.created_at,
            expires_at=session.expires_at,
        )

    @staticmethod
    def reset_session(db: Session, session_id: str) -> DemoSessionResponse:
        session = db.get(DemoSession, session_id)
        if not session:
            raise ResourceNotFoundException("DemoSession", session_id)

        # Cascade delete old entities belonging to this session
        db.execute(delete(User).where(User.demo_session_id == session_id))
        db.flush()

        # Re-seed
        primary_user = seed_demo_data(db, session, scenario=session.seed_scenario)
        db.commit()
        db.refresh(session)

        credentials = SessionCredentials(
            user_token=generate_session_token(session.id, primary_user.id, "user"),
            agent_token=generate_session_token(session.id, primary_user.id, "agent"),
            demo_control_token=generate_session_token(session.id, primary_user.id, "demo-control"),
        )

        return DemoSessionResponse(
            id=session.id,
            display_name=session.display_name,
            seed_scenario=session.seed_scenario,
            seed_version=session.seed_version,
            status=session.status,
            created_at=session.created_at,
            expires_at=session.expires_at,
            credentials=credentials,
        )

