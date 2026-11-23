"""Split bill and participant database models."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class SplitBill(Base):
    __tablename__ = "split_bills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    creator_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    payer_participant_id: Mapped[str] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    total_amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    service_fee_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    discount_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, SETTLED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    participants = relationship("SplitParticipant", back_populates="split_bill", cascade="all, delete-orphan")
    items = relationship("SplitItem", back_populates="split_bill", cascade="all, delete-orphan")
    collection_requests = relationship("SplitCollectionRequest", back_populates="split_bill", cascade="all, delete-orphan")


class SplitParticipant(Base):
    __tablename__ = "split_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    split_bill_id: Mapped[str] = mapped_column(String(36), ForeignKey("split_bills.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    share_amount_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    paid_amount_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)  # PENDING, SETTLED

    split_bill = relationship("SplitBill", back_populates="participants")
    assignments = relationship("SplitAssignment", back_populates="participant", cascade="all, delete-orphan")


class SplitItem(Base):
    __tablename__ = "split_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    split_bill_id: Mapped[str] = mapped_column(String(36), ForeignKey("split_bills.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    unit_price_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_price_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)

    split_bill = relationship("SplitBill", back_populates="items")
    assignments = relationship("SplitAssignment", back_populates="item", cascade="all, delete-orphan")


class SplitAssignment(Base):
    __tablename__ = "split_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    split_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("split_items.id", ondelete="CASCADE"), index=True, nullable=False)
    participant_id: Mapped[str] = mapped_column(String(36), ForeignKey("split_participants.id", ondelete="CASCADE"), index=True, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    item = relationship("SplitItem", back_populates="assignments")
    participant = relationship("SplitParticipant", back_populates="assignments")


class SplitCollectionRequest(Base):
    __tablename__ = "split_collection_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    split_bill_id: Mapped[str] = mapped_column(String(36), ForeignKey("split_bills.id", ondelete="CASCADE"), index=True, nullable=False)
    participant_id: Mapped[str] = mapped_column(String(36), ForeignKey("split_participants.id", ondelete="CASCADE"), index=True, nullable=False)
    requested_amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    collected_amount_vnd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="UNPAID", nullable=False)  # UNPAID, PAID, CANCELLED
    qr_payload: Mapped[str] = mapped_column(Text, nullable=False)
    payment_link: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    split_bill = relationship("SplitBill", back_populates="collection_requests")
    participant = relationship("SplitParticipant")
