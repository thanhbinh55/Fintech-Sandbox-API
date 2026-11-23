"""Demo Session database model."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class DemoSession(Base):
    __tablename__ = "demo_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(50), nullable=False, default="admin")
    seed_scenario: Mapped[str] = mapped_column(String(50), nullable=False, default="scenario_a")
    seed_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    users = relationship("User", back_populates="demo_session", cascade="all, delete-orphan")
    accounts = relationship("Account", back_populates="demo_session", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="demo_session", cascade="all, delete-orphan")
    offers = relationship("Offer", back_populates="demo_session", cascade="all, delete-orphan")
