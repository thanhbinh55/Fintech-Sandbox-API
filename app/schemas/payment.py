"""Payment intent, quote, approval, and execution schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PaymentIntentCreate(BaseModel):
    recipient_account_id: str = Field(..., description="Target simulated recipient account ID")
    amount_vnd: int = Field(..., gt=0, description="Principal payment amount in VND (strictly integer)")
    description: str = Field(..., min_length=1, max_length=255, description="Transfer note or bill description")
    merchant_id: Optional[str] = Field(default=None, description="Optional merchant identifier for category-specific offers")


class PaymentQuoteResponse(BaseModel):
    id: str
    payment_intent_id: str
    source_account_id: str
    source_display_name: str
    source_type: str
    amount_vnd: int
    fee_vnd: int
    immediate_discount_vnd: int
    amount_debited_vnd: int
    estimated_reward_vnd: int
    effective_cost_vnd: int
    eligible: bool
    eligibility_reason: str
    applied_offer_ids: List[str]
    applied_offer_names: List[str]
    expires_at: datetime
    recommended: bool = False
    explanation_codes: List[str] = Field(default_factory=list)


class PaymentApprovalRequest(BaseModel):
    quote_id: str = Field(..., description="ID of the approved payment quote")


class PaymentApprovalResponse(BaseModel):
    id: str
    payment_intent_id: str
    approved_quote_id: str
    actor_user_id: str
    approved_intent_version: int
    approved_payment_snapshot: Dict[str, Any]
    approved_at: datetime


class PaymentExecuteRequest(BaseModel):
    idempotency_key: Optional[str] = Field(default=None, description="Optional client idempotency key to prevent double execution")


class PaymentIntentResponse(BaseModel):
    id: str
    creator_user_id: str
    recipient_account_id: str
    recipient_display_name: Optional[str] = None
    amount_vnd: int
    currency: str = "VND"
    description: str
    merchant_id: Optional[str] = None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    approval: Optional[PaymentApprovalResponse] = None
    quotes: List[PaymentQuoteResponse] = Field(default_factory=list)


class PaymentExecuteResponse(BaseModel):
    payment_intent_id: str
    transaction_id: str
    status: str  # SIMULATED_SUCCESS, FAILED
    amount_transferred_vnd: int
    fee_vnd: int
    amount_debited_vnd: int
    source_account_id: str
    recipient_account_id: str
    completed_at: datetime
    provider_name: str = "internal_simulation"
    provider_reference_id: Optional[str] = None
    fallback_used: bool = False
    message: str = "Simulated transfer executed successfully in sandbox."

