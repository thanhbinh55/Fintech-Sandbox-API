"""Multi-turn Tool-Calling Agent Loop with Guardrails (adapted from Zalo AI Challenge ToolLoop)."""
from __future__ import annotations

import json
import time
from typing import Any

from google import genai
from google.genai import types

from app.agent_guards import ProposedToolCall, default_fintech_guards
from app.config import GEMINI_API_KEY, LLM_MODEL
from app.sandbox_bridge import SandboxAPIError, SandboxBridge, SessionState


COPILOT_SYSTEM_PROMPT = """Bạn là **MoMo AI Financial Copilot** — trợ lý tài chính thông minh hợp tác cùng người dùng trong không gian làm việc thanh toán hiện đại.

NGUYÊN TẮC CỐT LÕI (BẮT BUỘC TUÂN THỦ):
1. **Không bao giờ tự bịa số tài khoản hay số dư:** Mọi thao tác tìm người nhận, kiểm tra nguồn tiền, tạo nháp giao dịch, xếp hạng báo giá hay chia hóa đơn đều phải gọi qua các công cụ (`tools`) được cung cấp.
2. **Xử lý trùng tên người nhận (Scenario A — Ambiguity Handling):**
   - Trước khi tạo bản nháp chuyển tiền, LUÔN gọi `find_contacts(query)` trước.
   - Nếu `is_ambiguous: true` (ví dụ có cả "Nguyễn Minh" và "Trần Minh") và người dùng chưa nói rõ tên đầy đủ / ngân hàng / SĐT: **TUYỆT ĐỐI KHÔNG** gọi `create_payment_draft`. Hãy lịch sự liệt kê rõ từng ứng viên (kèm ngân hàng và SĐT) để hỏi lại người dùng chọn ai.
3. **Luôn lấy báo giá Smart Payment Routing (Scenario A & B):**
   - Ngay sau khi `create_payment_draft` thành công, LUÔN gọi tiếp `get_payment_quotes(payment_intent_id)` để lấy bảng xếp hạng các nguồn tiền tối ưu (Ví MoMo, Vietcombank, Techcombank Visa...) kèm phí, giảm giá, hoàn tiền và giải thích rõ vì sao nguồn #1 được khuyến nghị.
   - Nếu người dùng chỉ hỏi *"Thanh toán X đồng bằng nguồn nào có lợi nhất?"* mà chưa nêu tên người nhận, hãy gọi `get_payment_sources()` để kiểm tra nguồn tiền hiện có và gợi ý người dùng chọn người nhận (hoặc nếu họ chỉ định/nhắc tới giao dịch cụ thể thì tạo draft + gọi `get_payment_quotes` để công cụ xếp hạng tính toán chính xác).
4. **Chia hóa đơn nhóm chính xác (Scenario C — Split Bill):**
   - Khi người dùng yêu cầu chia hóa đơn ăn uống/nhóm, trích xuất đầy đủ `title`, `payer_name` (mặc định `"An"` nếu người dùng xưng "tôi/mình/tao" trong phiên demo), `participants`, `items` (với `unit_price_vnd`, `quantity`, `assigned_participant_names` rỗng nếu chia đều), `tax_vnd`, `service_fee_vnd`, `discount_vnd`, rồi gọi `create_split_bill`.
   - Số tiền luôn là số nguyên VND dương.
5. **Human-in-the-Loop (An toàn tuyệt đối):**
   - Bạn KHÔNG có quyền duyệt hay chuyển tiền thật. Sau khi tạo xong bản nháp và báo giá, hãy tóm tắt rõ ràng thông tin đơn và nhắc người dùng kiểm tra thẻ duyệt bên phải rồi bấm nút **"Xác nhận & Thanh toán"**.
6. **Ngắn gọn, thân thiện, tiếng Việt tự nhiên.**
"""


SANDBOX_TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="find_contacts",
            description="Tìm kiếm người nhận trong danh bạ theo tên, biệt danh hoặc số điện thoại (ví dụ: 'Minh', 'Lan', '0912345678'). Tự động phát hiện trùng tên.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Tên, biệt danh hoặc SĐT người nhận",
                    )
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_payment_sources",
            description="Lấy danh sách các nguồn tiền hiện có của người dùng (Ví MoMo, ngân hàng liên kết, thẻ tín dụng) kèm số dư khả dụng.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={}),
        ),
        types.FunctionDeclaration(
            name="create_payment_draft",
            description="Tạo bản nháp giao dịch chuyển tiền (trạng thái DRAFT). Chỉ tạo nháp, KHÔNG thực hiện thanh toán.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "recipient_id": types.Schema(
                        type=types.Type.STRING,
                        description="recipient_account_id (hoặc id contact) lấy từ kết quả find_contacts",
                    ),
                    "amount_vnd": types.Schema(
                        type=types.Type.INTEGER,
                        description="Số tiền cần chuyển (VND, số nguyên dương)",
                    ),
                    "note": types.Schema(
                        type=types.Type.STRING,
                        description="Lời nhắn hoặc nội dung chuyển khoản",
                    ),
                },
                required=["recipient_id", "amount_vnd", "note"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_payment_quotes",
            description="Tính toán và xếp hạng các phương thức thanh toán tối ưu cho một bản nháp (Smart Payment Routing: so sánh phí, giảm giá, cashback).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "payment_intent_id": types.Schema(
                        type=types.Type.STRING,
                        description="ID của bản nháp giao dịch từ create_payment_draft",
                    )
                },
                required=["payment_intent_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="create_split_bill",
            description="Tạo yêu cầu chia hóa đơn nhóm chính xác từng món hoặc chia đều bằng số nguyên VND, kèm thuế, phí dịch vụ và giảm giá.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title": types.Schema(type=types.Type.STRING, description="Tên hóa đơn"),
                    "payer_name": types.Schema(
                        type=types.Type.STRING,
                        description="Tên người đã ứng tiền trả trước (ví dụ: 'An')",
                    ),
                    "participants": types.Schema(
                        type=types.Type.ARRAY,
                        description="Danh sách người tham gia (tối thiểu 2)",
                        items=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "display_name": types.Schema(type=types.Type.STRING)
                            },
                            required=["display_name"],
                        ),
                    ),
                    "items": types.Schema(
                        type=types.Type.ARRAY,
                        description="Danh sách các món trong hóa đơn",
                        items=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "name": types.Schema(type=types.Type.STRING),
                                "unit_price_vnd": types.Schema(type=types.Type.INTEGER),
                                "quantity": types.Schema(type=types.Type.INTEGER),
                                "assigned_participant_names": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(type=types.Type.STRING),
                                    description="Tên những người dùng món này. Để rỗng [] nếu chia đều tất cả.",
                                ),
                            },
                            required=["name", "unit_price_vnd"],
                        ),
                    ),
                    "tax_vnd": types.Schema(type=types.Type.INTEGER),
                    "service_fee_vnd": types.Schema(type=types.Type.INTEGER),
                    "discount_vnd": types.Schema(type=types.Type.INTEGER),
                },
                required=["title", "payer_name", "participants", "items"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_transaction_history",
            description="Xem lịch sử giao dịch gần đây của phiên hiện tại.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "limit": types.Schema(type=types.Type.INTEGER),
                },
            ),
        ),
    ]
)


class FintechCopilotAgent:
    """Multi-turn tool-calling orchestrator combining Gemini + Guardrails + Fintech Sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        api_key: str = GEMINI_API_KEY,
        model_name: str = LLM_MODEL,
        max_steps: int = 6,
        max_blocked: int = 3,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing. Please set GEMINI_API_KEY.")
        self.bridge = bridge
        self.provider_name = "gemini"
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)
        self.guards = default_fintech_guards()
        self.max_steps = max_steps
        self.max_blocked = max_blocked

    async def _execute_tool(
        self, session_id: str, name: str, args: dict[str, Any]
    ) -> Any:
        if name == "find_contacts":
            return await self.bridge.find_contacts(session_id, args["query"])
        if name == "get_payment_sources":
            return await self.bridge.get_payment_sources(session_id)
        if name == "create_payment_draft":
            return await self.bridge.create_payment_draft(
                session_id=session_id,
                recipient_id=args["recipient_id"],
                amount_vnd=args["amount_vnd"],
                note=args["note"],
            )
        if name == "get_payment_quotes":
            return await self.bridge.get_payment_quotes(
                session_id=session_id,
                payment_intent_id=args["payment_intent_id"],
            )
        if name == "create_split_bill":
            return await self.bridge.create_split_bill(session_id, args)
        if name == "get_transaction_history":
            return await self.bridge.get_transaction_history(
                session_id, limit=int(args.get("limit", 10))
            )
        raise ValueError(f"Unsupported tool: {name}")

    async def run_turn(self, session_id: str, user_text: str) -> dict[str, Any]:
        state: SessionState = self.bridge.get_session(session_id)
        t0 = time.perf_counter()

        # Build conversation contents from session history + current user message
        contents: list[types.Content] = []
        for msg in state.chat_history[-10:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg["text"])])
            )
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_text)])
        )

        executed_in_turn: list[dict[str, Any]] = []
        tool_trace: list[dict[str, Any]] = []
        blocked_count = 0
        assistant_reply = ""

        config = types.GenerateContentConfig(
            system_instruction=COPILOT_SYSTEM_PROMPT,
            tools=[SANDBOX_TOOLS],
            temperature=0.1,
        )

        for _ in range(self.max_steps):
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )

            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                break

            contents.append(candidate.content)
            fn_calls = [p.function_call for p in candidate.content.parts if p.function_call]

            if not fn_calls:
                assistant_reply = (response.text or "").strip()
                break

            fn_response_parts: list[types.Part] = []
            for fc in fn_calls:
                name = fc.name
                args = dict(fc.args) if fc.args else {}
                proposed = ProposedToolCall(name=name, arguments=args)

                guard_rejection = None
                rejected_by = None
                for g in self.guards:
                    msg = g.check(proposed, state, user_text, executed_in_turn)
                    if msg:
                        guard_rejection = msg
                        rejected_by = g.name
                        break

                if guard_rejection:
                    blocked_count += 1
                    trace_item = {
                        "tool": name,
                        "args": args,
                        "status": "BLOCKED",
                        "guard": rejected_by,
                        "message": guard_rejection,
                    }
                    tool_trace.append(trace_item)
                    result_payload = {"ok": False, "error": guard_rejection}
                else:
                    t_tool = time.perf_counter()
                    try:
                        out = await self._execute_tool(session_id, name, proposed.arguments)
                        executed_in_turn.append({"name": name, "arguments": proposed.arguments})
                        tool_trace.append(
                            {
                                "tool": name,
                                "args": proposed.arguments,
                                "status": "OK",
                                "latency_ms": round((time.perf_counter() - t_tool) * 1000, 2),
                                "result": out,
                            }
                        )
                        result_payload = {"ok": True, "data": out}
                    except SandboxAPIError as exc:
                        tool_trace.append(
                            {
                                "tool": name,
                                "args": proposed.arguments,
                                "status": "API_ERROR",
                                "message": str(exc),
                            }
                        )
                        result_payload = {"ok": False, "error": str(exc)}

                fn_response_parts.append(
                    types.Part.from_function_response(
                        name=name,
                        response=json.loads(json.dumps(result_payload, default=str)),
                    )
                )

            contents.append(types.Content(role="user", parts=fn_response_parts))
            if blocked_count > self.max_blocked:
                assistant_reply = "Yêu cầu bị chặn bởi lớp bảo vệ an toàn. Vui lòng nêu rõ hơn người nhận hoặc số tiền."
                break

        if not assistant_reply:
            assistant_reply = "Đã xử lý xong thông tin giao dịch. Vui lòng kiểm tra chi tiết ở khung bên phải."

        # Persist concise conversation turns for multi-turn disambiguation
        state.chat_history.append({"role": "user", "text": user_text})
        state.chat_history.append({"role": "assistant", "text": assistant_reply})

        llm_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "assistant_reply": assistant_reply,
            "tool_trace": tool_trace,
            "active_draft": state.active_draft,
            "quotes": state.active_quotes,
            "active_split_bill": state.active_split_bill,
            "ambiguous_contacts": state.ambiguous_contacts,
            "llm_latency_ms": llm_ms,
            "llm_provider": self.provider_name,
            "llm_model": self.model_name,
        }
