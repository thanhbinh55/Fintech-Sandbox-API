"""Account database model."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)  # EWALLET, SIMULATED_BANK, SIMULATED_CARD, INTERNAL_SETTLEMENT
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(5), default="VND", nullable=False)
    available_balance_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    credit_limit_vnd: Mapped[int] = mapped_column(BigInteger, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    demo_session = relationship("DemoSession", back_populates="accounts")
    owner = relationship("User", back_populates="accounts")
    ledger_entries = relationship("LedgerEntry", back_populates="account")

