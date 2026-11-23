"""Transaction and double-entry ledger database models."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    payment_intent_id: Mapped[str] = mapped_column(String(36), ForeignKey("payment_intents.id", ondelete="SET NULL"), unique=True, nullable=True)
    source_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    destination_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="SUCCESS", nullable=False)  # SUCCESS, FAILED
    idempotency_key: Mapped[str] = mapped_column(String(100), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    source_account = relationship("Account", foreign_keys=[source_account_id])
    destination_account = relationship("Account", foreign_keys=[destination_account_id])
    ledger_entries = relationship("LedgerEntry", back_populates="transaction", cascade="all, delete-orphan")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id", ondelete="CASCADE"), index=True, nullable=False)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # DEBIT, CREDIT
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    transaction = relationship("Transaction", back_populates="ledger_entries")
    account = relationship("Account", back_populates="ledger_entries")

