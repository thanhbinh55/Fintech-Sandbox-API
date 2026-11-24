from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import sqlite3
import time
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
    seen_recipient_account_ids: list[str] = field(default_factory=list)
    last_contact_search: dict[str, Any] | None = None
    active_draft: dict[str, Any] | None = None
    active_quotes: list[dict[str, Any]] = field(default_factory=list)
    active_split_bill: dict[str, Any] | None = None
    ambiguous_contacts: list[dict[str, Any]] = field(default_factory=list)
    last_execution: dict[str, Any] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "SessionState":
        data = json.loads(raw)
        return cls(**data)


def filter_user_accounts(accounts: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Hide internal sandbox settlement accounts from end-user wallet UI."""
    if not accounts:
        return []
    return [a for a in accounts if a.get("account_type") != "INTERNAL_SETTLEMENT"]


class SandboxBridge:
    """Async HTTP bridge connecting Developer B's AI Copilot to Developer A's Fintech Sandbox API.

    Production enhancements:
    - Persistent httpx.AsyncClient connection pool managed in FastAPI lifespan.
    - SQLite-backed session persistence (survives restarts/reloads).
    - Auto-chains create_payment_draft -> get_payment_quotes to eliminate extra LLM round-trip.
    - Enforces strict token isolation (agent_token vs user_token vs demo_control_token).
    """

    def __init__(
        self,
        base_url: str = SANDBOX_BASE_URL,
        timeout_s: float = 15.0,
        db_path: str | Path = "./sessions_state.db",
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.db_path = Path(db_path)
        self.sessions: dict[str, SessionState] = {}
        self._client: httpx.AsyncClient | None = None
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS copilot_sessions (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    def _save_session(self, state: SessionState) -> None:
        self.sessions[state.session_id] = state
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO copilot_sessions (session_id, state_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (state.session_id, state.to_json(), time.time()),
            )
            conn.commit()

    def _load_session(self, session_id: str) -> SessionState | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT state_json FROM copilot_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        state = SessionState.from_json(row[0])
        self.sessions[session_id] = state
        return state

    async def startup(self) -> None:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout_s,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )

    async def shutdown(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> tuple[httpx.AsyncClient, bool]:
        if self._client is not None and not self._client.is_closed:
            return self._client, False
        return httpx.AsyncClient(timeout=self.timeout_s), True

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

        client, should_close = await self._get_client()
        try:
            resp = await client.request(method, url, params=params, json=json_data, headers=headers)
        finally:
            if should_close:
                await client.aclose()

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
        if state is not None:
            return state
        loaded = self._load_session(session_id)
        if loaded is not None:
            return loaded
        raise KeyError(f"Unknown session_id: {session_id}")

    def save_session(self, state: SessionState) -> None:
        self._save_session(state)

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
        self._save_session(state)
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
        self._save_session(state)
        return state

    # -------------------------------------------------------------------------
    # AGENT-SCOPED TOOLS (agent_token ONLY)
    # -------------------------------------------------------------------------

    async def find_contacts(self, session_id: str, query: str) -> dict[str, Any]:
        state = self.get_session(session_id)
        data = await self._request(
            "GET", "/contacts", token=state.agent_token, params={"q": query}
        )
        seen_ids = set(state.seen_recipient_account_ids)
        for m in data.get("matches", []):
            if m.get("id"):
                state.seen_contacts[m["id"]] = m
            if m.get("recipient_account_id"):
                seen_ids.add(m["recipient_account_id"])
        state.seen_recipient_account_ids = sorted(seen_ids)
        state.last_contact_search = data
        state.ambiguous_contacts = data.get("matches", []) if data.get("is_ambiguous") else []
        self._save_session(state)
        return data

    async def get_payment_sources(self, session_id: str) -> list[dict[str, Any]]:
        state = self.get_session(session_id)
        return await self._request("GET", "/payment-sources", token=state.agent_token)

    def _find_contact_meta(self, state: SessionState, recipient_account_id: str) -> dict[str, Any] | None:
        for c in state.seen_contacts.values():
            if c.get("recipient_account_id") == recipient_account_id:
                return {
                    "display_name": c.get("display_name"),
                    "alias": c.get("alias"),
                    "bank_name": c.get("bank_name") or "Ví MoMo",
                    "phone_number": c.get("phone_number"),
                }
        return None

    async def create_payment_draft(
        self,
        session_id: str,
        recipient_id: str,
        amount_vnd: int,
        note: str,
        merchant_id: str | None = None,
    ) -> dict[str, Any]:
        state = self.get_session(session_id)
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

        draft = await self._request(
            "POST", "/payment-intents", token=state.agent_token, json_data=payload
        )
        recipient_meta = self._find_contact_meta(state, resolved_recipient_account_id)
        if recipient_meta:
            draft["recipient_meta"] = recipient_meta

        # Auto-chain quotes in the same backend call to eliminate an extra LLM round-trip
        quotes_resp = await self._request(
            "POST",
            f"/payment-intents/{draft['id']}/quotes",
            token=state.agent_token,
        )
        quotes = quotes_resp.get("quotes", []) if isinstance(quotes_resp, dict) else quotes_resp
        draft["quotes"] = quotes
        draft["status"] = "QUOTED"

        state.active_draft = draft
        state.active_quotes = quotes
        state.ambiguous_contacts = []
        state.last_execution = None
        self._save_session(state)
        return {"draft": draft, "quotes": quotes}

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
        self._save_session(state)
        return {"payment_intent_id": payment_intent_id, "quotes": quotes}

    async def create_split_bill(
        self, session_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        state = self.get_session(session_id)
        data = await self._request(
            "POST", "/split-bills", token=state.agent_token, json_data=payload
        )
        state.active_split_bill = data
        self._save_session(state)
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
        accounts = await self._request("GET", "/me/accounts", token=state.user_token)
        return filter_user_accounts(accounts)

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
        self._save_session(state)
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
        self._save_session(state)
        return {"settlement": res, "split_bill": updated_bill}
