"""VietQR Provider Adapter (NAPAS EMVCo standard collection QR code)."""
import urllib.parse
from app.core.config import get_settings
from app.providers.base import ProviderQRRequest, ProviderQRResult, QRProvider


def calculate_crc16_ccitt(data: str) -> str:
    """Compute standard EMVCo CRC16-CCITT checksum (Polynomial 0x1021, Initial 0xFFFF)."""
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def emv_tlv(tag: str, value: str) -> str:
    """Format Tag-Length-Value entry for EMVCo standard."""
    val_bytes = value.encode("utf-8")
    return f"{tag}{len(val_bytes):02d}{value}"


class VietQRProvider(QRProvider):
    """Generates NAPAS EMVCo-compliant VietQR payload strings and quick link images.

    Distinctly labeled as an external display presentation QR that does not
    automatically bypass or settle internal sandbox state.
    """

    def __init__(self):
        self.settings = get_settings()

    def is_available(self) -> bool:
        return True

    def generate_collection_qr(self, request: ProviderQRRequest) -> ProviderQRResult:
        bank_bin = request.bank_bin or self.settings.VIETQR_DEFAULT_BANK_BIN
        account_no = request.recipient_account_number or "9988776655"
        template = self.settings.VIETQR_DEFAULT_TEMPLATE
        amount_str = str(request.requested_amount_vnd)
        narrative = f"SPLIT_{request.collection_request_id[:8]}"

        # 1. Construct EMVCo Payload
        # Tag 00: Payload Format Indicator (01)
        # Tag 01: Point of Initiation Method (12 = Dynamic with Amount)
        # Tag 38: NAPAS Beneficiary Sub-TLV (00=GUID, 01=Bank BIN, 02=Account No)
        napas_guid = emv_tlv("00", "A000000727")
        napas_bin = emv_tlv("01", bank_bin)
        napas_acc = emv_tlv("02", account_no)
        tag38_value = f"{napas_guid}{napas_bin}{napas_acc}"

        tag00 = emv_tlv("00", "01")
        tag01 = emv_tlv("01", "12")
        tag38 = emv_tlv("38", tag38_value)
        tag52 = emv_tlv("52", "0000")  # MCC
        tag53 = emv_tlv("53", "704")   # VND Currency code
        tag54 = emv_tlv("54", amount_str)
        tag58 = emv_tlv("58", "VN")    # Country Code
        tag59 = emv_tlv("59", request.recipient_name[:25])
        tag60 = emv_tlv("60", "HCM")   # City

        # Tag 62: Additional Data Template (Sub-tag 08: Purpose/AddInfo)
        tag62_sub08 = emv_tlv("08", narrative)
        tag62 = emv_tlv("62", tag62_sub08)

        # Concatenate prior to CRC
        raw_before_crc = f"{tag00}{tag01}{tag38}{tag52}{tag53}{tag54}{tag58}{tag59}{tag60}{tag62}6304"
        crc_val = calculate_crc16_ccitt(raw_before_crc)
        emvco_qr_string = f"{raw_before_crc}{crc_val}"

        # 2. Quick Link image URL
        query_params = urllib.parse.urlencode({
            "amount": amount_str,
            "addInfo": narrative,
            "accountName": request.recipient_name,
        })
        vietqr_image_url = f"https://img.vietqr.io/image/{bank_bin}-{account_no}-{template}.png?{query_params}"

        return ProviderQRResult(
            provider_name="vietqr",
            qr_payload=emvco_qr_string,
            payment_link=vietqr_image_url,
            is_external_payment_rail=True,
            notice=(
                "VIETQR STANDARD DISPLAY QR: Generated per NAPAS EMVCo QR specifications. "
                "This external QR is for mobile banking display and does NOT auto-settle the sandbox ledger."
            ),
        )

