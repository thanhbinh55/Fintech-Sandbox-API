"""SePay Sandbox Payment Provider Adapter (Optional external payment gateway)."""
import base64
from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import logger
from app.providers.base import PaymentProvider, ProviderPaymentRequest, ProviderPaymentResult
from app.providers.payment.internal_simulation_provider import InternalSimulationProvider


class SePaySandboxProvider(PaymentProvider):
    """Adapter for SePay Sandbox Payment Gateway.

    Gated by credentials and environment configuration. External communication failures
    safely fall back to InternalSimulationProvider so demo environments are never blocked.
    """

    def __init__(self):
        self.settings = get_settings()
        self.internal_provider = InternalSimulationProvider()

    def is_available(self) -> bool:
        """Check if official SePay Sandbox credentials are present."""
        return bool(self.settings.SEPAY_MERCHANT_ID and self.settings.SEPAY_SECRET_KEY)

    def execute_payment(
        self,
        db: Session,
        request: ProviderPaymentRequest,
    ) -> ProviderPaymentResult:
        # Step 1: Always execute atomic ledger and balance check internally first
        # This guarantees financial integrity and prevents overdrawing (Requirement 5)
        internal_result = self.internal_provider.execute_payment(db, request)

        # Step 2: If credentials are not configured, return internal simulation with explicit notice
        if not self.is_available():
            logger.info("SePay credentials not configured. Executing via internal simulation mode.")
            return ProviderPaymentResult(
                success=internal_result.success,
                transaction_id=internal_result.transaction_id,
                provider_name="sepay_sandbox (unconfigured_fallback)",
                provider_reference_id=f"sim_{internal_result.transaction_id}",
                amount_transferred_vnd=internal_result.amount_transferred_vnd,
                fee_vnd=internal_result.fee_vnd,
                amount_debited_vnd=internal_result.amount_debited_vnd,
                source_account_id=internal_result.source_account_id,
                destination_account_id=internal_result.destination_account_id,
                completed_at=internal_result.completed_at,
                metadata={
                    **internal_result.metadata,
                    "sepay_status": "SKIPPED_NO_CREDENTIALS",
                    "notice": "SePay credentials not set in environment. Fallback to sandbox simulation active.",
                },
                fallback_used=True,
                message="Executed via sandbox simulation (SePay credentials not configured).",
            )

        # Step 3: Call official SePay Sandbox API
        auth_str = f"{self.settings.SEPAY_MERCHANT_ID}:{self.settings.SEPAY_SECRET_KEY}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/json",
            "User-Agent": "FintechSandbox-API/0.1.0",
        }

        payload = {
            "merchant_id": self.settings.SEPAY_MERCHANT_ID,
            "order_id": request.payment_intent_id,
            "amount": request.amount_vnd,
            "currency": "VND",
            "order_description": request.description or "Sandbox Transfer",
            "custom_data": {
                "session_id": request.session_id,
                "transaction_id": internal_result.transaction_id,
            },
        }

        try:
            with httpx.Client(timeout=self.settings.SEPAY_TIMEOUT_SECONDS) as client:
                response = client.post(
                    self.settings.SEPAY_CHECKOUT_URL,
                    json=payload,
                    headers=headers,
                )

                if response.status_code in (200, 201):
                    res_data = response.json()
                    sepay_ref = res_data.get("checkout_id") or res_data.get("id") or f"sp_{request.payment_intent_id[:8]}"
                    return ProviderPaymentResult(
                        success=True,
                        transaction_id=internal_result.transaction_id,
                        provider_name="sepay_sandbox",
                        provider_reference_id=str(sepay_ref),
                        amount_transferred_vnd=internal_result.amount_transferred_vnd,
                        fee_vnd=internal_result.fee_vnd,
                        amount_debited_vnd=internal_result.amount_debited_vnd,
                        source_account_id=internal_result.source_account_id,
                        destination_account_id=internal_result.destination_account_id,
                        completed_at=internal_result.completed_at,
                        metadata={
                            **internal_result.metadata,
                            "sepay_response": res_data,
                            "checkout_url": res_data.get("checkout_url"),
                        },
                        fallback_used=False,
                        message="Transfer authorized and registered with SePay Sandbox.",
                    )
                else:
                    logger.warning(
                        f"SePay Sandbox API returned HTTP {response.status_code}: {response.text}. Using fallback."
                    )
                    return self._handle_failure_fallback(
                        internal_result,
                        reason=f"SePay returned HTTP {response.status_code}",
                    )

        except (httpx.TimeoutException, httpx.RequestError) as net_err:
            logger.warning(f"SePay Sandbox network error: {net_err}. Executing safe fallback.")
            return self._handle_failure_fallback(
                internal_result,
                reason=f"Network connectivity error: {type(net_err).__name__}",
            )

    def _handle_failure_fallback(
        self, internal_result: ProviderPaymentResult, reason: str
    ) -> ProviderPaymentResult:
        if not self.settings.SEPAY_FALLBACK_TO_SIMULATION:
            raise RuntimeError(f"SePay Sandbox failed and fallback is disabled: {reason}")

        return ProviderPaymentResult(
            success=internal_result.success,
            transaction_id=internal_result.transaction_id,
            provider_name="sepay_sandbox (fallback_simulated)",
            provider_reference_id=f"fallback_{internal_result.transaction_id}",
            amount_transferred_vnd=internal_result.amount_transferred_vnd,
            fee_vnd=internal_result.fee_vnd,
            amount_debited_vnd=internal_result.amount_debited_vnd,
            source_account_id=internal_result.source_account_id,
            destination_account_id=internal_result.destination_account_id,
            completed_at=internal_result.completed_at,
            metadata={
                **internal_result.metadata,
                "fallback_reason": reason,
                "fallback_timestamp": datetime.now(timezone.utc).isoformat(),
            },
            fallback_used=True,
            message=f"Simulated transfer succeeded (SePay fallback used: {reason}).",
        )

    def get_transaction_status(self, reference_id: str) -> Dict[str, Any]:
        if not self.is_available():
            return {"reference_id": reference_id, "status": "SIMULATED", "provider": "sepay_sandbox"}

        auth_str = f"{self.settings.SEPAY_MERCHANT_ID}:{self.settings.SEPAY_SECRET_KEY}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {"Authorization": f"Basic {b64_auth}"}

        try:
            with httpx.Client(timeout=self.settings.SEPAY_TIMEOUT_SECONDS) as client:
                res = client.get(
                    f"{self.settings.SEPAY_BASE_URL}/orders/{reference_id}",
                    headers=headers,
                )
                if res.status_code == 200:
                    return res.json()
        except Exception as e:
            logger.warning(f"Failed to query SePay transaction status: {e}")

        return {"reference_id": reference_id, "status": "UNKNOWN", "provider": "sepay_sandbox"}
