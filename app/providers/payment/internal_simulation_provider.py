"""Internal Simulation Payment Provider (Mandatory, default provider)."""
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.models import Transaction
from app.providers.base import PaymentProvider, ProviderPaymentRequest, ProviderPaymentResult
from app.services.ledger_service import LedgerService


class InternalSimulationProvider(PaymentProvider):
    """Executes payments against internal simulated accounts using the double-entry ledger."""

    def is_available(self) -> bool:
        return True

    def execute_payment(
        self,
        db: Session,
        request: ProviderPaymentRequest,
    ) -> ProviderPaymentResult:
        # Atomic transfer execution with double-entry ledger entries
        tx = LedgerService.execute_transfer(
            db=db,
            session_id=request.session_id,
            source_account_id=request.source_account_id,
            destination_account_id=request.destination_account_id,
            amount_vnd=request.amount_vnd,
            fee_vnd=request.fee_vnd,
            immediate_discount_vnd=request.immediate_discount_vnd,
            payment_intent_id=request.payment_intent_id,
            idempotency_key=request.idempotency_key,
        )

        amount_debited = request.amount_vnd + request.fee_vnd - request.immediate_discount_vnd

        return ProviderPaymentResult(
            success=True,
            transaction_id=tx.id,
            provider_name="internal_simulation",
            provider_reference_id=tx.id,
            amount_transferred_vnd=tx.amount_vnd,
            fee_vnd=tx.fee_vnd,
            amount_debited_vnd=amount_debited,
            source_account_id=tx.source_account_id,
            destination_account_id=tx.destination_account_id,
            completed_at=tx.completed_at or datetime.now(timezone.utc),
            metadata={"clearing": "INTERNAL_SETTLEMENT"},
            fallback_used=False,
            message="Simulated transfer executed successfully in sandbox ledger.",
        )

    def get_transaction_status(self, reference_id: str) -> Dict[str, Any]:
        return {
            "reference_id": reference_id,
            "status": "SUCCESS",
            "provider": "internal_simulation",
        }

