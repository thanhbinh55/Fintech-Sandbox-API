"""Bill splitting schemas."""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SplitItemInput(BaseModel):
    name: str = Field(..., description="Item description (e.g., Cơm tấm, Nước cam)")
    unit_price_vnd: int = Field(..., gt=0, description="Unit price in integer VND")
    quantity: int = Field(default=1, gt=0, description="Quantity")
    assigned_participant_names: List[str] = Field(
        default_factory=list,
        description="Names of participants sharing this item. Empty means shared equally by all.",
    )


class SplitParticipantInput(BaseModel):
    display_name: str = Field(..., description="Participant name")
    user_id: Optional[str] = Field(default=None, description="Linked user ID if participant has an internal account")


class SplitBillCreate(BaseModel):
    title: str = Field(default="Bữa ăn trưa", description="Bill title or event name")
    payer_name: str = Field(..., description="Name of the person who originally paid the full bill")
    participants: List[SplitParticipantInput] = Field(..., min_length=2, description="List of at least two participants")
    items: List[SplitItemInput] = Field(..., min_length=1, description="Itemized bill entries")
    tax_vnd: int = Field(default=0, ge=0, description="Total VAT or tax in VND to be shared proportionally")
    service_fee_vnd: int = Field(default=0, ge=0, description="Service charge in VND to be shared proportionally")
    discount_vnd: int = Field(default=0, ge=0, description="Global discount in VND to be subtracted proportionally")


class SplitParticipantShareResponse(BaseModel):
    participant_id: str
    display_name: str
    is_payer: bool
    subtotal_items_vnd: int
    allocated_tax_vnd: int
    allocated_fee_vnd: int
    allocated_discount_vnd: int
    total_share_vnd: int
    amount_paid_vnd: int
    remaining_balance_vnd: int
    status: str  # SETTLED, PENDING


class SplitCollectionRequestResponse(BaseModel):
    request_id: str
    participant_id: str
    participant_name: str
    requested_amount_vnd: int
    collected_amount_vnd: int
    status: str  # UNPAID, PAID, CANCELLED
    sandbox_payment_link: str
    qr_payload: str
    provider_name: str = "internal_sandbox"
    is_external_payment_rail: bool = False
    created_at: datetime


class SplitBillResponse(BaseModel):
    id: str
    title: str
    creator_user_id: str
    payer_participant_id: str
    total_bill_amount_vnd: int
    tax_vnd: int
    service_fee_vnd: int
    discount_vnd: int
    status: str  # DRAFT, ACTIVE, SETTLED
    participant_shares: List[SplitParticipantShareResponse]
    collection_requests: List[SplitCollectionRequestResponse] = Field(default_factory=list)
    created_at: datetime


class SplitStatusResponse(BaseModel):
    split_bill_id: str
    total_bill_amount_vnd: int
    total_collected_vnd: int
    remaining_to_collect_vnd: int
    is_fully_settled: bool
    participant_statuses: List[SplitParticipantShareResponse]


class SplitSettleRequest(BaseModel):
    collected_amount_vnd: Optional[int] = Field(
        default=None,
        description="Amount collected in VND. If omitted, marks full remaining amount as paid.",
    )

