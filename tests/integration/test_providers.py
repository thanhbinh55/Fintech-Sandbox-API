"""Comprehensive unit and integration tests for Payment and QR Providers."""
import os
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.core.config import get_settings
from app.models import Account, User
from app.providers.base import ProviderPaymentRequest, ProviderQRRequest
from app.providers.factory import get_payment_provider, get_qr_provider
from app.providers.payment.internal_simulation_provider import InternalSimulationProvider
from app.providers.payment.sepay_sandbox_provider import SePaySandboxProvider
from app.providers.qr.internal_sandbox_qr_provider import InternalSandboxQRProvider
from app.providers.qr.vietqr_provider import VietQRProvider, calculate_crc16_ccitt


def test_internal_simulation_provider_execution(db_session, demo_session):
    primary_acc = db_session.query(Account).filter_by(demo_session_id=demo_session.id, account_type="EWALLET").first()
    recipient_acc = db_session.query(Account).filter(
        Account.demo_session_id == demo_session.id,
        Account.owner_user_id != primary_acc.owner_user_id,
        Account.account_type == "EWALLET",
    ).first()

    provider = InternalSimulationProvider()
    assert provider.is_available() is True

    req = ProviderPaymentRequest(
        session_id=demo_session.id,
        payment_intent_id=None,
        source_account_id=primary_acc.id,
        destination_account_id=recipient_acc.id,
        amount_vnd=50000,
        fee_vnd=0,
        immediate_discount_vnd=0,
        description="Internal provider test",
        idempotency_key="prov-idem-01",
    )
    res = provider.execute_payment(db_session, req)
    assert res.success is True
    assert res.provider_name == "internal_simulation"
    assert res.fallback_used is False
    assert res.amount_transferred_vnd == 50000


def test_sepay_provider_unconfigured_fallback(db_session, demo_session):
    primary_acc = db_session.query(Account).filter_by(demo_session_id=demo_session.id, account_type="EWALLET").first()
    recipient_acc = db_session.query(Account).filter(
        Account.demo_session_id == demo_session.id,
        Account.owner_user_id != primary_acc.owner_user_id,
    ).first()

    provider = SePaySandboxProvider()
    # Unconfigured credentials in default test env
    provider.settings.SEPAY_MERCHANT_ID = None
    provider.settings.SEPAY_SECRET_KEY = None
    assert provider.is_available() is False

    req = ProviderPaymentRequest(
        session_id=demo_session.id,
        payment_intent_id=None,
        source_account_id=primary_acc.id,
        destination_account_id=recipient_acc.id,
        amount_vnd=40000,
        fee_vnd=0,
        immediate_discount_vnd=0,
        description="Fallback test",
    )
    res = provider.execute_payment(db_session, req)

    assert res.success is True
    assert res.fallback_used is True
    assert "fallback" in res.provider_name.lower()
    assert res.metadata.get("sepay_status") == "SKIPPED_NO_CREDENTIALS"


def test_sepay_provider_mocked_success(db_session, demo_session):
    primary_acc = db_session.query(Account).filter_by(demo_session_id=demo_session.id, account_type="EWALLET").first()
    recipient_acc = db_session.query(Account).filter(
        Account.demo_session_id == demo_session.id,
        Account.owner_user_id != primary_acc.owner_user_id,
    ).first()

    provider = SePaySandboxProvider()
    provider.settings.SEPAY_MERCHANT_ID = "test_merchant_001"
    provider.settings.SEPAY_SECRET_KEY = "test_secret_key_123"
    assert provider.is_available() is True

    # Mock successful response from SePay Sandbox Checkout API
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "checkout_id": "sp_chk_99887766",
            "order_id": "intent-mock-01",
            "checkout_url": "https://pay-sandbox.sepay.vn/checkout/sp_chk_99887766",
            "status": "INITIATED",
        },
        request=httpx.Request("POST", provider.settings.SEPAY_CHECKOUT_URL),
    )

    with patch("httpx.Client.post", return_value=mock_resp):
        req = ProviderPaymentRequest(
            session_id=demo_session.id,
            payment_intent_id=None,
            source_account_id=primary_acc.id,
            destination_account_id=recipient_acc.id,
            amount_vnd=100000,
            fee_vnd=0,
            immediate_discount_vnd=0,
            description="Mocked SePay test",
        )
        res = provider.execute_payment(db_session, req)

        assert res.success is True
        assert res.provider_name == "sepay_sandbox"
        assert res.provider_reference_id == "sp_chk_99887766"
        assert res.fallback_used is False
        assert res.metadata["checkout_url"] == "https://pay-sandbox.sepay.vn/checkout/sp_chk_99887766"


def test_sepay_provider_network_failure_safe_fallback(db_session, demo_session):
    """External network error must NOT crash or break the payment transaction."""
    primary_acc = db_session.query(Account).filter_by(demo_session_id=demo_session.id, account_type="EWALLET").first()
    recipient_acc = db_session.query(Account).filter(
        Account.demo_session_id == demo_session.id,
        Account.owner_user_id != primary_acc.owner_user_id,
    ).first()

    provider = SePaySandboxProvider()
    provider.settings.SEPAY_MERCHANT_ID = "test_merchant_001"
    provider.settings.SEPAY_SECRET_KEY = "test_secret_key_123"
    provider.settings.SEPAY_FALLBACK_TO_SIMULATION = True

    # Simulate network timeout
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Connection timed out")):
        req = ProviderPaymentRequest(
            session_id=demo_session.id,
            payment_intent_id=None,
            source_account_id=primary_acc.id,
            destination_account_id=recipient_acc.id,
            amount_vnd=60000,
            fee_vnd=0,
            immediate_discount_vnd=0,
            description="Timeout test",
        )
        res = provider.execute_payment(db_session, req)

        # Payment MUST still succeed internally via fallback
        assert res.success is True
        assert res.fallback_used is True
        assert "fallback" in res.provider_name.lower()
        assert "TimeoutException" in res.metadata["fallback_reason"]


def test_internal_sandbox_qr_provider():
    provider = InternalSandboxQRProvider()
    assert provider.is_available() is True

    req = ProviderQRRequest(
        split_bill_id="bill-01",
        collection_request_id="req-99",
        participant_name="Bình",
        requested_amount_vnd=75000,
        recipient_name="An",
    )
    res = provider.generate_collection_qr(req)
    assert res.provider_name == "internal_sandbox"
    assert "SANDBOX_VND_PAYMENT:split_bill_id=bill-01" in res.qr_payload
    assert "https://sandbox.wallet.local/pay/split/req-99" == res.payment_link
    assert res.is_external_payment_rail is False


def test_vietqr_provider_emvco_payload_and_crc():
    provider = VietQRProvider()
    assert provider.is_available() is True

    req = ProviderQRRequest(
        split_bill_id="bill-vietqr-01",
        collection_request_id="req-vietqr-88",
        participant_name="Bình",
        requested_amount_vnd=150000,
        recipient_name="Nguyen Van An",
        recipient_account_number="0123456789",
        bank_bin="970436",
    )
    res = provider.generate_collection_qr(req)

    assert res.provider_name == "vietqr"
    assert res.is_external_payment_rail is True
    assert "img.vietqr.io" in res.payment_link
    assert "970436-0123456789" in res.payment_link

    # Check EMVCo payload structure
    qr = res.qr_payload
    assert qr.startswith("000201010212")  # Tag 00 (01), Tag 01 (12)
    assert "A000000727" in qr            # NAPAS GUID
    assert "5303704" in qr               # Currency VND
    assert "5406150000" in qr            # Amount 150000
    assert "5802VN" in qr                # Country VN
    assert "6304" in qr                  # CRC Tag

    # Verify CRC checksum calculation matches
    crc_idx = qr.rfind("6304")
    prefix = qr[:crc_idx + 4]
    expected_crc = calculate_crc16_ccitt(prefix)
    actual_crc = qr[crc_idx + 4:]
    assert actual_crc == expected_crc


def test_api_execution_with_sepay_provider_override(client, user_headers):
    """Verify that setting PAYMENT_PROVIDER=sepay runs execute endpoint through SePay adapter seamlessly."""
    contact_res = client.get("/v1/contacts?q=Lan", headers=user_headers)
    recipient_acc_id = contact_res.json()["data"]["matches"][0]["recipient_account_id"]

    draft = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": recipient_acc_id, "amount_vnd": 45000, "description": "SePay API test"},
        headers=user_headers,
    ).json()["data"]

    quotes = client.post(f"/v1/payment-intents/{draft['id']}/quotes", headers=user_headers).json()["data"]["quotes"]
    client.post(f"/v1/payment-intents/{draft['id']}/approve", json={"quote_id": quotes[0]["id"]}, headers=user_headers)

    settings = get_settings()
    old_provider = settings.PAYMENT_PROVIDER
    try:
        settings.PAYMENT_PROVIDER = "sepay"
        exec_res = client.post(
            f"/v1/payment-intents/{draft['id']}/execute",
            json={"idempotency_key": "sepay-api-override-01"},
            headers=user_headers,
        )
        assert exec_res.status_code == 200
        data = exec_res.json()["data"]
        assert data["status"] == "SIMULATED_SUCCESS"
        assert "sepay" in data["provider_name"]
    finally:
        settings.PAYMENT_PROVIDER = old_provider


def test_api_split_bill_with_vietqr_override(client, agent_headers):
    """Verify that setting QR_PROVIDER=vietqr generates VietQR payload and link on split bill creation."""
    settings = get_settings()
    old_qr = settings.QR_PROVIDER
    try:
        settings.QR_PROVIDER = "vietqr"
        bill_res = client.post(
            "/v1/split-bills",
            json={
                "title": "VietQR Test Bill",
                "payer_name": "An",
                "participants": [{"display_name": "An"}, {"display_name": "Bình"}],
                "items": [{"name": "Phở bò", "unit_price_vnd": 60000, "quantity": 2}],
                "tax_vnd": 0,
                "service_fee_vnd": 0,
                "discount_vnd": 0,
            },
            headers=agent_headers,
        )
        assert bill_res.status_code == 200
        bill = bill_res.json()["data"]
        col_req = bill["collection_requests"][0]

        # Verify VietQR details
        assert col_req["provider_name"] == "vietqr"
        assert col_req["is_external_payment_rail"] is True
        assert "img.vietqr.io" in col_req["sandbox_payment_link"]

        # Check QR endpoint
        qr_detail = client.get(
            f"/v1/split-bills/{bill['id']}/requests/{col_req['request_id']}/qr",
            headers=agent_headers,
        ).json()["data"]
        assert qr_detail["provider_name"] == "vietqr"
        assert qr_detail["is_external_payment_rail"] is True
        assert "VIETQR STANDARD DISPLAY QR" in qr_detail["simulation_note"]
    finally:
        settings.QR_PROVIDER = old_qr


@pytest.mark.skipif(
    not os.environ.get("SEPAY_MERCHANT_ID"),
    reason="Live SePay Sandbox credentials (SEPAY_MERCHANT_ID) not provided in environment.",
)
def test_sepay_live_sandbox_smoke():
    """Live smoke test executing against SePay Sandbox only when real credentials exist in env."""
    settings = get_settings()
    provider = SePaySandboxProvider()
    assert provider.is_available() is True

    status_data = provider.get_transaction_status("test-nonexistent-ref")
    assert status_data is not None
