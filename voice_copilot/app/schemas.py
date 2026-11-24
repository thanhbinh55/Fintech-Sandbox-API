from typing import Literal, Optional
from urllib.parse import quote
from pydantic import BaseModel, Field


class PaymentOrder(BaseModel):
    intent: Literal["transfer", "bill_split", "unknown"] = Field(
        description="Ý định của người dùng: transfer (chuyển tiền), bill_split (chia tiền nhóm), unknown (không rõ)"
    )
    recipient_name: Optional[str] = Field(
        default=None, description="Tên người nhận nếu được nhắc tới"
    )
    account_number: Optional[str] = Field(
        default=None,
        description="Số tài khoản ngân hàng hoặc SĐT MoMo (chỉ gồm các chữ số, không khoảng trắng/dấu gạch)",
    )
    bank_code: Optional[str] = Field(
        default=None,
        description="Mã ngân hàng chuẩn Napas (VCB, TCB, MB, ACB, BIDV, ICB, VPB, TPB, STB, HDB, VIB, OCB, MSB, SHB, MOMO...)",
    )
    bank_name: Optional[str] = Field(
        default=None, description="Tên đầy đủ của ngân hàng hoặc ví MoMo"
    )
    amount: Optional[int] = Field(
        default=None, description="Tổng số tiền giao dịch dạng số nguyên VND"
    )
    note: Optional[str] = Field(
        default=None, description="Lời nhắn hoặc nội dung chuyển khoản rõ ràng"
    )
    split_count: Optional[int] = Field(
        default=None, description="Số người chia tiền nếu intent là bill_split"
    )
    amount_per_person: Optional[int] = Field(
        default=None,
        description="Số tiền mỗi người phải trả (làm tròn nguyên VND) nếu intent là bill_split",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Danh sách các trường bắt buộc còn thiếu để thực hiện thanh toán (account_number, bank_code, amount)",
    )
    fraud_warning: Optional[str] = Field(
        default=None,
        description="Cảnh báo rủi ro lừa đảo nếu phát hiện dấu hiệu bất thường hoặc mạo danh",
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Độ tự tin của trích xuất (0.0 - 1.0)"
    )


class STTResponse(BaseModel):
    transcript: str
    stt_latency_ms: float


class ParseRequest(BaseModel):
    text: str


class VoicePaymentResponse(BaseModel):
    transcript: str
    order: PaymentOrder
    vietqr_url: Optional[str] = None
    stt_latency_ms: Optional[float] = None
    llm_latency_ms: float
    total_latency_ms: float
    llm_provider: str
    llm_model: str


def build_vietqr_url(order: PaymentOrder) -> Optional[str]:
    final_amount = order.amount_per_person or order.amount
    if (
        not order.bank_code
        or order.bank_code.upper() == "MOMO"
        or not order.account_number
        or not final_amount
        or final_amount <= 0
    ):
        return None
    encoded_note = quote(order.note or "")
    return (
        f"https://img.vietqr.io/image/{order.bank_code.upper()}-"
        f"{order.account_number}-compact2.png?amount={final_amount}&addInfo={encoded_note}"
    )
