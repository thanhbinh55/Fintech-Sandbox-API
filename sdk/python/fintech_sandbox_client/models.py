"""Data models for Python SDK."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class Contact(BaseModel):
    id: str
    display_name: str
    alias: Optional[str] = None
    phone_number: Optional[str] = None
    recipient_account_id: str
    bank_name: Optional[str] = None


class ContactSearchResult(BaseModel):
    query: str
    matches: List[Contact]
    is_ambiguous: bool
    clarification_message: Optional[str] = None


class PaymentSource(BaseModel):
    source_id: str
    account_type: str
    display_name: str
    account_number_masked: str
    currency: str = "VND"
    available_funds_vnd: int
    is_credit: bool
    credit_limit_vnd: Optional[int] = None
    enabled: bool
    icon_hint: str


class PaymentQuote(BaseModel):
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
    recommended: bool
    explanation_codes: List[str]


class PaymentIntent(BaseModel):
    id: str
    creator_user_id: str
    recipient_account_id: str
    recipient_display_name: Optional[str] = None
    amount_vnd: int
    currency: str
    description: str
    merchant_id: Optional[str] = None
    status: str
    version: int
    quotes: List[PaymentQuote] = []


class SplitBill(BaseModel):
    id: str
    title: str
    total_bill_amount_vnd: int
    tax_vnd: int
    service_fee_vnd: int
    discount_vnd: int
    status: str
    participant_shares: List[Dict[str, Any]]
    collection_requests: List[Dict[str, Any]] = []


class SplitStatus(BaseModel):
    split_bill_id: str
    total_bill_amount_vnd: int
    total_collected_vnd: int
    remaining_to_collect_vnd: int
    is_fully_settled: bool
    participant_statuses: List[Dict[str, Any]]
