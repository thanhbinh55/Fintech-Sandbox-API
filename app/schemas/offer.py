"""Offer and reward schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class OfferResponse(BaseModel):
    id: str
    display_name: str
    code: str
    eligible_source_types: List[str]
    eligible_merchant_ids: Optional[List[str]] = None
    minimum_amount_vnd: int
    maximum_discount_vnd: int
    reward_type: str  # INSTANT_DISCOUNT, CASHBACK
    reward_value_percent: Optional[float] = None
    reward_value_flat_vnd: Optional[int] = None
    starts_at: datetime
    expires_at: datetime
    active: bool
    is_fictional_demo: bool = True
