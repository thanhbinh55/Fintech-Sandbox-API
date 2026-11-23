"""Offer database model."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    eligible_source_types: Mapped[list] = mapped_column(SQLITE_JSON, default=list, nullable=False)
    eligible_merchant_ids: Mapped[list] = mapped_column(SQLITE_JSON, nullable=True)
    minimum_amount_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    maximum_discount_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reward_type: Mapped[str] = mapped_column(String(30), nullable=False)  # INSTANT_DISCOUNT, CASHBACK
    reward_value_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    reward_value_flat_vnd: Mapped[int] = mapped_column(BigInteger, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usage_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    demo_session = relationship("DemoSession", back_populates="offers")
