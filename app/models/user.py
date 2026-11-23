"""User database model."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="PRIMARY_USER")  # PRIMARY_USER, PARTICIPANT
    phone_number: Mapped[str] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    demo_session = relationship("DemoSession", back_populates="users")
    accounts = relationship("Account", back_populates="owner", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="owner", cascade="all, delete-orphan")
