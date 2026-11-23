"""Payment intent, quote, and approval database models."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class PaymentIntent(Base):
    __tablename__ = "payment_intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    creator_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    recipient_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(5), default="VND", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)  # DRAFT, QUOTED, AWAITING_APPROVAL, APPROVED, PROCESSING, SIMULATED_SUCCESS, FAILED, CANCELLED, EXPIRED
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    recipient_account = relationship("Account", foreign_keys=[recipient_account_id])
    quotes = relationship("PaymentQuote", back_populates="payment_intent", cascade="all, delete-orphan")
    approval = relationship("PaymentApproval", back_populates="payment_intent", uselist=False, cascade="all, delete-orphan")


class PaymentQuote(Base):
    __tablename__ = "payment_quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_intent_id: Mapped[str] = mapped_column(String(36), ForeignKey("payment_intents.id", ondelete="CASCADE"), index=True, nullable=False)
    source_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    immediate_discount_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    amount_debited_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    estimated_reward_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    effective_cost_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    eligibility_reason: Mapped[str] = mapped_column(Text, nullable=False)
    applied_offer_ids: Mapped[list] = mapped_column(SQLITE_JSON, default=list, nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    payment_intent = relationship("PaymentIntent", back_populates="quotes")
    source_account = relationship("Account", foreign_keys=[source_account_id])


class PaymentApproval(Base):
    __tablename__ = "payment_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_intent_id: Mapped[str] = mapped_column(String(36), ForeignKey("payment_intents.id", ondelete="CASCADE"), unique=True, nullable=False)
    approved_quote_id: Mapped[str] = mapped_column(String(36), ForeignKey("payment_quotes.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    approved_intent_version: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_payment_snapshot: Mapped[dict] = mapped_column(SQLITE_JSON, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    payment_intent = relationship("PaymentIntent", back_populates="approval")
    approved_quote = relationship("PaymentQuote", foreign_keys=[approved_quote_id])
