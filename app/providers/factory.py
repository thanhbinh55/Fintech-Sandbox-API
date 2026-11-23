"""Provider Factory for Payment and QR Providers."""
from typing import Optional
from app.core.config import get_settings
from app.providers.base import PaymentProvider, QRProvider
from app.providers.payment.internal_simulation_provider import InternalSimulationProvider
from app.providers.payment.sepay_sandbox_provider import SePaySandboxProvider
from app.providers.qr.internal_sandbox_qr_provider import InternalSandboxQRProvider
from app.providers.qr.vietqr_provider import VietQRProvider


def get_payment_provider(provider_override: Optional[str] = None) -> PaymentProvider:
    """Instantiate configured payment provider based on environment or explicit override."""
    settings = get_settings()
    provider_name = (provider_override or settings.PAYMENT_PROVIDER).lower().strip()

    if provider_name in ("sepay", "sepay_sandbox"):
        return SePaySandboxProvider()

    return InternalSimulationProvider()


def get_qr_provider(provider_override: Optional[str] = None) -> QRProvider:
    """Instantiate configured QR provider based on environment or explicit override."""
    settings = get_settings()
    provider_name = (provider_override or settings.QR_PROVIDER).lower().strip()

    if provider_name in ("vietqr", "viet_qr", "napas"):
        return VietQRProvider()

    return InternalSandboxQRProvider()
