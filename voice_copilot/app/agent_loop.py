"""Multi-turn Tool-Calling Agent Loop with Async Gemini, Low-Latency Thinking Budget, Retry/Fallback & Guardrails."""
from __future__ import annotations

import asyncio
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
3. **Tạo nháp & Smart Payment Routing (Scenario A & B):**
   - Lưu ý tối ưu tốc độ: Công cụ `create_payment_draft` **ĐÃ TỰ ĐỘNG TÍNH VÀ TRẢ VỀ LUÔN `quotes` (bảng xếp hạng nguồn tiền)** trong cùng kết quả. Vì vậy khi `create_payment_draft` đã trả về `quotes`, **KHÔNG cần gọi lại `get_payment_quotes` nữa** — hãy dùng ngay dữ liệu `quotes` đó để giải thích ngắn gọn vì sao nguồn #1 được khuyến nghị (chi phí hiệu quả, giảm giá, hoàn tiền, phí).
   - Chỉ gọi `get_payment_quotes` riêng nếu cần tính lại báo giá cho một `payment_intent_id` đã có từ trước.
   - Nếu người dùng chỉ hỏi *"Thanh toán X đồng bằng nguồn nào có lợi nhất?"* mà chưa nêu tên người nhận, hãy gọi `get_payment_sources()` để kiểm tra nguồn tiền hiện có và gợi ý người dùng chọn người nhận.
4. **Chia hóa đơn nhóm chính xác (Scenario C — Split Bill):**
   - Khi người dùng yêu cầu chia hóa đơn ăn uống/nhóm, trích xuất đầy đủ `title`, `payer_name` (mặc định `"An"` nếu người dùng xưng "tôi/mình/tao" trong phiên demo), `participants`, `items` (với `unit_price_vnd`, `quantity`, `assigned_participant_names` rỗng nếu chia đều), `tax_vnd`, `service_fee_vnd`, `discount_vnd`, rồi gọi `create_split_bill`.
   - Số tiền luôn là số nguyên VND dương.
5. **Human-in-the-Loop (An toàn tuyệt đối):**
   - Bạn KHÔNG có quyền duyệt hay chuyển tiền thật. Sau khi tạo xong bản nháp và báo giá, hãy tóm tắt ngắn gọn thông tin đơn và nhắc người dùng bấm **"Xác nhận & Thanh toán ngay"** ở thẻ duyệt.
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
            description="Tạo bản nháp giao dịch chuyển tiền (DRAFT) VÀ tự động trả về bảng xếp hạng nguồn tiền tối ưu (quotes). Chỉ tạo nháp, KHÔNG thực hiện thanh toán.",
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
            description="Tính lại hoặc lấy bảng xếp hạng nguồn tiền cho một payment_intent_id đã tồn tại (không cần gọi nếu create_payment_draft vừa trả về quotes).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "payment_intent_id": types.Schema(
                        type=types.Type.STRING,
                        description="ID của bản nháp giao dịch",
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
    """Async multi-turn tool-calling orchestrator combining Gemini + Guardrails + Fintech Sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        api_key: str = GEMINI_API_KEY,
        model_name: str = LLM_MODEL,
        fallback_model: str = "gemini-2.5-flash-lite",
        max_steps: int = 6,
        max_blocked: int = 3,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing. Please set GEMINI_API_KEY.")
        self.bridge = bridge
        self.provider_name = "gemini"
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.client = genai.Client(api_key=api_key)
        self.guards = default_fintech_guards()
        self.max_steps = max_steps
        self.max_blocked = max_blocked

    def _build_system_instruction(self, state: SessionState) -> str:
        ctx: dict[str, Any] = {}
        if state.seen_contacts:
            ctx["known_contacts"] = [
                {
                    "recipient_account_id": c.get("recipient_account_id"),
                    "display_name": c.get("display_name"),
                    "bank_name": c.get("bank_name") or "Ví MoMo",
                    "phone_number": c.get("phone_number"),
                }
                for c in state.seen_contacts.values()
            ]
        if state.active_draft:
            ctx["active_draft"] = {
                "id": state.active_draft.get("id"),
                "amount_vnd": state.active_draft.get("amount_vnd"),
                "status": state.active_draft.get("status"),
            }
        if not ctx:
            return COPILOT_SYSTEM_PROMPT
        return (
            COPILOT_SYSTEM_PROMPT
            + "\n\n[SESSION_CONTEXT ĐÃ TRA CỨU TRONG PHIÊN NÀY - DÙNG ĐỂ GỌI TOOL KHI NGƯỜI DÙNG CHỌN]:\n"
            + json.dumps(ctx, ensure_ascii=False)
        )

    def _build_config(
        self, state: SessionState, use_thinking_zero: bool = True
    ) -> types.GenerateContentConfig:
        kwargs: dict[str, Any] = {
            "system_instruction": self._build_system_instruction(state),
            "tools": [SANDBOX_TOOLS],
            "temperature": 0.1,
        }
        if use_thinking_zero and "2.5" in self.model_name:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        return types.GenerateContentConfig(**kwargs)

    async def _generate_with_resilience(
        self, state: SessionState, contents: list[types.Content]
    ) -> tuple[Any, str]:
        """Async Gemini call with 10s per-attempt timeout, zero-thinking latency, and fast fallback."""
        config = self._build_config(state, use_thinking_zero=True)
        models_to_try = [self.model_name]
        if self.fallback_model and self.fallback_model != self.model_name:
            models_to_try.append(self.fallback_model)
        models_to_try.append(self.model_name)

        last_exc: Exception | None = None
        for idx, active_model in enumerate(models_to_try):
            if idx == 2:
                await asyncio.sleep(0.3)
            try:
                resp = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=active_model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=10.0,
                )
                cand = resp.candidates[0] if resp.candidates else None
                parts = (cand.content.parts or []) if (cand and cand.content) else []
                if parts:
                    return resp, active_model
                last_exc = RuntimeError(f"Empty parts returned by {active_model}")
            except Exception as exc:
                last_exc = exc
                if "thinking" in str(exc).lower():
                    config = self._build_config(state, use_thinking_zero=False)
        assert last_exc is not None
        raise last_exc

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
        llm_rounds = 0
        used_model = self.model_name
        assistant_reply = ""

        for _ in range(self.max_steps):
            llm_rounds += 1
            response, used_model = await self._generate_with_resilience(state, contents)

            candidate = response.candidates[0] if response.candidates else None
            parts = (candidate.content.parts or []) if (candidate and candidate.content) else []
            if not parts:
                break

            contents.append(candidate.content)
            fn_calls = [p.function_call for p in parts if p.function_call]

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
                    tool_trace.append(
                        {
                            "tool": name,
                            "args": args,
                            "status": "BLOCKED",
                            "guard": rejected_by,
                            "message": guard_rejection,
                        }
                    )
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
            assistant_reply = "Đã xử lý xong thông tin giao dịch. Vui lòng kiểm tra chi tiết ở thẻ duyệt."

        state.chat_history.append({"role": "user", "text": user_text})
        state.chat_history.append({"role": "assistant", "text": assistant_reply})
        self.bridge.save_session(state)

        llm_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "assistant_reply": assistant_reply,
            "tool_trace": tool_trace,
            "active_draft": state.active_draft,
            "quotes": state.active_quotes,
            "active_split_bill": state.active_split_bill,
            "ambiguous_contacts": state.ambiguous_contacts,
            "llm_latency_ms": llm_ms,
            "llm_rounds": llm_rounds,
            "llm_provider": self.provider_name,
            "llm_model": used_model,
        }
