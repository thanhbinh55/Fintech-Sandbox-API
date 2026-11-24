from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import SANDBOX_BASE_URL


class SandboxAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


@dataclass
class SessionState:
    session_id: str
    scenario: str
    agent_token: str
    user_token: str
    demo_control_token: str
    chat_history: list[dict[str, str]] = field(default_factory=list)
    seen_contacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    seen_recipient_account_ids: set[str] = field(default_factory=set)
    last_contact_search: dict[str, Any] | None = None
    active_draft: dict[str, Any] | None = None
    active_quotes: list[dict[str, Any]] = field(default_factory=list)
    active_split_bill: dict[str, Any] | None = None
    ambiguous_contacts: list[dict[str, Any]] = field(default_factory=list)
    last_execution: dict[str, Any] | None = None


class SandboxBridge:
    """Async HTTP bridge connecting Developer B's AI Copilot to Developer A's Fintech Sandbox API.

    Enforces strict token isolation:
    - Agent tool calls ONLY use `agent_token` (read/draft/quote).
    - Human approval/execution ONLY uses `user_token` (never exposed to LLM).
    - Session resets ONLY use `demo_control_token`.
    """

    def __init__(self, base_url: str = SANDBOX_BASE_URL, timeout_s: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.sessions: dict[str, SessionState] = {}

    async def _request(
        self,
        method: str,
        path: str,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.request(method, url, params=params, json=json_data, headers=headers)
            try:
                body = resp.json()
            except Exception:
                resp.raise_for_status()
                return {}

            if resp.status_code >= 400 or not body.get("success", False):
                err = body.get("error") or body.get("detail") or resp.text
                if isinstance(err, dict):
                    msg = err.get("message") or str(err)
                else:
                    msg = str(err)
                raise SandboxAPIError(resp.status_code, msg, detail=body)
            return body.get("data")

    def get_session(self, session_id: str) -> SessionState:
        state = self.sessions.get(session_id)
        if not state:
            raise KeyError(f"Unknown session_id: {session_id}")
        return state

    async def create_session(
        self, scenario: str = "scenario_a", display_name: str = "MoMo Voice Copilot"
    ) -> SessionState:
        data = await self._request(
            "POST",
            "/demo/sessions",
            json_data={"scenario": scenario, "display_name": display_name},
        )
        creds = data["credentials"]
        state = SessionState(
            session_id=data["id"],
            scenario=data.get("seed_scenario", scenario),
            agent_token=creds["agent_token"],
            user_token=creds["user_token"],
            demo_control_token=creds["demo_control_token"],
        )
        self.sessions[state.session_id] = state
        return state

    async def reset_session(self, session_id: str) -> SessionState:
        state = self.get_session(session_id)
        await self._request("POST", "/demo/reset", token=state.demo_control_token)
        state.chat_history.clear()
        state.seen_contacts.clear()
        state.seen_recipient_account_ids.clear()
        state.last_contact_search = None
        state.active_draft = None
        state.active_quotes = []
        state.active_split_bill = None
        state.ambiguous_contacts = []
        state.last_execution = None
        return state

    # -------------------------------------------------------------------------
    # AGENT-SCOPED TOOLS (agent_token ONLY)
    # -------------------------------------------------------------------------

    async def find_contacts(self, session_id: str, query: str) -> dict[str, Any]:
        state = self.get_session(session_id)
        data = await self._request(
            "GET", "/contacts", token=state.agent_token, params={"q": query}
        )
        for m in data.get("matches", []):
            if m.get("id"):
                state.seen_contacts[m["id"]] = m
            if m.get("recipient_account_id"):
                state.seen_recipient_account_ids.add(m["recipient_account_id"])
        state.last_contact_search = data
        if data.get("is_ambiguous"):
            state.ambiguous_contacts = data.get("matches", [])
        else:
            state.ambiguous_contacts = []
        return data

    async def get_payment_sources(self, session_id: str) -> list[dict[str, Any]]:
        state = self.get_session(session_id)
        return await self._request("GET", "/payment-sources", token=state.agent_token)

    async def create_payment_draft(
        self,
        session_id: str,
        recipient_id: str,
        amount_vnd: int,
        note: str,
        merchant_id: str | None = None,
    ) -> dict[str, Any]:
        state = self.get_session(session_id)
        # Resolve if caller passed contact.id instead of recipient_account_id
        resolved_recipient_account_id = recipient_id
        if recipient_id in state.seen_contacts:
            resolved_recipient_account_id = state.seen_contacts[recipient_id]["recipient_account_id"]

        payload: dict[str, Any] = {
            "recipient_account_id": resolved_recipient_account_id,
            "amount_vnd": amount_vnd,
            "description": note,
        }
        if merchant_id:
            payload["merchant_id"] = merchant_id

        data = await self._request(
            "POST", "/payment-intents", token=state.agent_token, json_data=payload
        )
        state.active_draft = data
        state.active_quotes = data.get("quotes", [])
        state.ambiguous_contacts = []
        state.last_execution = None
        return data

    async def get_payment_quotes(self, session_id: str, payment_intent_id: str) -> dict[str, Any]:
        state = self.get_session(session_id)
        data = await self._request(
            "POST",
            f"/payment-intents/{payment_intent_id}/quotes",
            token=state.agent_token,
        )
        quotes = data.get("quotes", []) if isinstance(data, dict) else data
        state.active_quotes = quotes
        if state.active_draft and state.active_draft.get("id") == payment_intent_id:
            state.active_draft["quotes"] = quotes
            state.active_draft["status"] = "QUOTED"
        return {"payment_intent_id": payment_intent_id, "quotes": quotes}

    async def create_split_bill(
        self, session_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        state = self.get_session(session_id)
        data = await self._request(
            "POST", "/split-bills", token=state.agent_token, json_data=payload
        )
        state.active_split_bill = data
        return data

    async def get_transaction_history(
        self, session_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        state = self.get_session(session_id)
        return await self._request(
            "GET",
            "/transactions",
            token=state.agent_token,
            params={"limit": limit, "offset": 0},
        )

    # -------------------------------------------------------------------------
    # USER-SCOPED ACTIONS (user_token ONLY - NEVER exposed to LLM)
    # -------------------------------------------------------------------------

    async def get_account_snapshot(self, session_id: str) -> list[dict[str, Any]]:
        state = self.get_session(session_id)
        return await self._request("GET", "/me/accounts", token=state.user_token)

    async def approve_and_execute_payment(
        self,
        session_id: str,
        payment_intent_id: str,
        quote_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        state = self.get_session(session_id)
        approval = await self._request(
            "POST",
            f"/payment-intents/{payment_intent_id}/approve",
            token=state.user_token,
            json_data={"quote_id": quote_id},
        )
        exec_payload = {"idempotency_key": idempotency_key} if idempotency_key else {}
        execution = await self._request(
            "POST",
            f"/payment-intents/{payment_intent_id}/execute",
            token=state.user_token,
            json_data=exec_payload,
        )
        accounts = await self.get_account_snapshot(session_id)
        state.last_execution = execution
        if state.active_draft and state.active_draft.get("id") == payment_intent_id:
            state.active_draft["status"] = execution.get("status", "SIMULATED_SUCCESS")
        return {
            "approval": approval,
            "execution": execution,
            "accounts": accounts,
        }

    async def settle_split_share(
        self, session_id: str, split_id: str, request_id: str
    ) -> dict[str, Any]:
        state = self.get_session(session_id)
        res = await self._request(
            "POST",
            f"/split-bills/{split_id}/requests/{request_id}/settle",
            token=state.user_token,
            json_data={},
        )
        updated_bill = await self._request(
            "GET", f"/split-bills/{split_id}", token=state.user_token
        )
        state.active_split_bill = updated_bill
        return {"settlement": res, "split_bill": updated_bill}
