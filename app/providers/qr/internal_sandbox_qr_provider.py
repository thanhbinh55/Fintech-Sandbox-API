"""Internal Sandbox QR Provider (Mandatory, default QR provider)."""
from app.providers.base import ProviderQRRequest, ProviderQRResult, QRProvider


class InternalSandboxQRProvider(QRProvider):
    """Generates internal sandbox URI payloads and test links for bill splitting collection."""

    def is_available(self) -> bool:
        return True

    def generate_collection_qr(self, request: ProviderQRRequest) -> ProviderQRResult:
        qr_payload = (
            f"SANDBOX_VND_PAYMENT:split_bill_id={request.split_bill_id}&"
            f"request_id={request.collection_request_id}&"
            f"amount={request.requested_amount_vnd}&"
            f"recipient={request.recipient_name}"
        )
        payment_link = f"https://sandbox.wallet.local/pay/split/{request.collection_request_id}"

        return ProviderQRResult(
            provider_name="internal_sandbox",
            qr_payload=qr_payload,
            payment_link=payment_link,
            is_external_payment_rail=False,
            notice="Sandbox simulated QR payload for internal test payments only. Real banking QR is not generated.",
        )
