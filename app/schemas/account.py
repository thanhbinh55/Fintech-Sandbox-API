"""Account and payment source schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    id: str
    owner_user_id: str
    account_type: str  # EWALLET, SIMULATED_BANK, SIMULATED_CARD, INTERNAL_SETTLEMENT
    display_name: str
    account_number: str
    currency: str = "VND"
    available_balance_vnd: int
    credit_limit_vnd: Optional[int] = None
    enabled: bool
    created_at: datetime


class PaymentSourceResponse(BaseModel):
    source_id: str
    account_type: str
    display_name: str
    account_number_masked: str
    currency: str = "VND"
    available_funds_vnd: int
    is_credit: bool = False
    credit_limit_vnd: Optional[int] = None
    enabled: bool
    icon_hint: str

