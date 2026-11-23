"""Abstract base classes and data transfer schemas for Payment and QR Providers."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


class ProviderPaymentRequest(BaseModel):
    session_id: str
    payment_intent_id: Optional[str] = None
    source_account_id: str
    destination_account_id: str
    amount_vnd: int
    fee_vnd: int = 0
    immediate_discount_vnd: int = 0
    description: str = ""
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProviderPaymentResult(BaseModel):
    success: bool
    transaction_id: str
    provider_name: str
    provider_reference_id: Optional[str] = None
    amount_transferred_vnd: int
    fee_vnd: int
    amount_debited_vnd: int
    source_account_id: str
    destination_account_id: str
    completed_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
    fallback_used: bool = False
    message: str = "Payment executed successfully."


class PaymentProvider(ABC):
    """Abstract interface for payment processing providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if credentials and configuration for this provider are ready."""
        pass

    @abstractmethod
    def execute_payment(
        self,
        db: Session,
        request: ProviderPaymentRequest,
    ) -> ProviderPaymentResult:
        """Execute payment.

        Must guarantee atomic ledger mutation, balance updates, and idempotency.
        """
        pass

    @abstractmethod
    def get_transaction_status(
        self,
        reference_id: str,
    ) -> Dict[str, Any]:
        """Query status of a transaction with the provider."""
        pass


class ProviderQRRequest(BaseModel):
    split_bill_id: str
    collection_request_id: str
    participant_name: str
    requested_amount_vnd: int
    recipient_name: str
    recipient_account_number: Optional[str] = None
    bank_bin: Optional[str] = None
    description: str = ""


class ProviderQRResult(BaseModel):
    provider_name: str  # "internal_sandbox" | "vietqr"
    qr_payload: str
    payment_link: str
    is_external_payment_rail: bool = False
    notice: str = ""


class QRProvider(ABC):
    """Abstract interface for collection QR and payment link generation."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the QR provider is configured and available."""
        pass

    @abstractmethod
    def generate_collection_qr(
        self,
        request: ProviderQRRequest,
    ) -> ProviderQRResult:
        """Generate QR payload and payment link for a bill share."""
        pass
