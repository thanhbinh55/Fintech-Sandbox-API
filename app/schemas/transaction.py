"""Transaction and ledger schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class LedgerEntryResponse(BaseModel):
    id: str
    account_id: str
    direction: str  # DEBIT, CREDIT
    amount_vnd: int
    created_at: datetime


class TransactionResponse(BaseModel):
    id: str
    payment_intent_id: Optional[str] = None
    source_account_id: str
    source_display_name: Optional[str] = None
    destination_account_id: str
    destination_display_name: Optional[str] = None
    amount_vnd: int
    fee_vnd: int
    status: str  # SUCCESS, FAILED
    idempotency_key: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    ledger_entries: List[LedgerEntryResponse] = Field(default_factory=list)
