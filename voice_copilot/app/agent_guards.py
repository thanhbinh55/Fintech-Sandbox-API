"""Fintech Agent Guardrails (adapted from Zalo AI Challenge Protocol-based Guards).

Each guard validates a proposed LLM tool call before it reaches the Fintech Sandbox API.
A guard returns None to allow the call, or a rejection message fed back to the LLM so it self-corrects.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.sandbox_bridge import SessionState


AGENT_ALLOWED_TOOLS = {
    "find_contacts",
    "get_payment_sources",
    "create_payment_draft",
    "get_payment_quotes",
    "create_split_bill",
    "get_transaction_history",
}

WRITE_TOOLS = {"create_payment_draft", "create_split_bill"}


@dataclass
class ProposedToolCall:
    name: str
    arguments: dict[str, Any]


class Guard(Protocol):
    name: str

    def check(
        self,
        call: ProposedToolCall,
        state: SessionState,
        user_text: str,
        executed_in_turn: list[dict[str, Any]],
    ) -> str | None: ...


class AllowedToolGuard:
    """Strictly restricts LLM to agent-safe tools; blocks any approval/execution attempt."""

    name = "allowed_tool"

    def check(
        self,
        call: ProposedToolCall,
        state: SessionState,
        user_text: str,
        executed_in_turn: list[dict[str, Any]],
    ) -> str | None:
        if call.name not in AGENT_ALLOWED_TOOLS:
            return (
                f"BLOCKED: Tool '{call.name}' is forbidden for AI Agent. "
                "Human confirmation via user token is mandatory for payment approval/execution."
            )
        if not isinstance(call.arguments, dict):
            return "BLOCKED: Tool arguments must be a JSON object."
        return None


def _coerce_strict_int(value: Any, field_name: str, allow_zero: bool = False) -> tuple[int | None, str | None]:
    if isinstance(value, bool):
        return None, f"'{field_name}' cannot be boolean."
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        if not value.is_integer():
            return None, f"'{field_name}' must be an integer VND amount (got {value})."
        parsed = int(value)
    elif isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace(".", "")
        if not cleaned.lstrip("-").isdigit():
            return None, f"'{field_name}' must be a valid integer VND string (got {value!r})."
        parsed = int(cleaned)
    else:
        return None, f"'{field_name}' must be an integer VND amount."

    if allow_zero:
        if parsed < 0:
            return None, f"'{field_name}' must be >= 0 (got {parsed})."
    else:
        if parsed <= 0:
            return None, f"'{field_name}' must be > 0 VND (got {parsed})."
    return parsed, None


class FinancialSchemaGuard:
    """Validates and normalizes strict integer VND schemas before calling Sandbox API."""

    name = "financial_schema"

    def check(
        self,
        call: ProposedToolCall,
        state: SessionState,
        user_text: str,
        executed_in_turn: list[dict[str, Any]],
    ) -> str | None:
        args = call.arguments
        if call.name == "find_contacts":
            q = args.get("query")
            if not isinstance(q, str) or not q.strip():
                return "Validation error: 'query' must be a non-empty string."
            args["query"] = q.strip()

        elif call.name == "create_payment_draft":
            for req_field in ("recipient_id", "amount_vnd", "note"):
                if req_field not in args or args[req_field] in (None, ""):
                    return f"Validation error: missing required field '{req_field}'."
            amount, err = _coerce_strict_int(args["amount_vnd"], "amount_vnd", allow_zero=False)
            if err:
                return f"Validation error: {err}"
            args["amount_vnd"] = amount
            args["note"] = str(args["note"]).strip()[:255]

        elif call.name == "get_payment_quotes":
            pid = args.get("payment_intent_id")
            if not isinstance(pid, str) or not pid.strip():
                return "Validation error: 'payment_intent_id' must be a non-empty string."

        elif call.name == "create_split_bill":
            if not isinstance(args.get("title"), str) or not args["title"].strip():
                args["title"] = "Chia hóa đơn nhóm"
            if not isinstance(args.get("payer_name"), str) or not args["payer_name"].strip():
                return "Validation error: 'payer_name' is required."

            participants = args.get("participants")
            if not isinstance(participants, list) or len(participants) < 2:
                return "Validation error: 'participants' must contain at least 2 people."
            normalized_participants = []
            for p in participants:
                if isinstance(p, str):
                    normalized_participants.append({"display_name": p.strip()})
                elif isinstance(p, dict) and p.get("display_name"):
                    normalized_participants.append({"display_name": str(p["display_name"]).strip()})
                else:
                    return "Validation error: each participant must have 'display_name'."
            args["participants"] = normalized_participants

            items = args.get("items")
            if not isinstance(items, list) or len(items) < 1:
                return "Validation error: 'items' must contain at least 1 item."
            for idx, item in enumerate(items):
                if not isinstance(item, dict) or not item.get("name"):
                    return f"Validation error: items[{idx}] requires 'name'."
                price, err = _coerce_strict_int(item.get("unit_price_vnd"), f"items[{idx}].unit_price_vnd")
                if err:
                    return f"Validation error: {err}"
                item["unit_price_vnd"] = price
                qty_raw = item.get("quantity", 1)
                qty, err = _coerce_strict_int(qty_raw, f"items[{idx}].quantity")
                if err:
                    return f"Validation error: {err}"
                item["quantity"] = qty
                if item.get("assigned_participant_names") is None:
                    item["assigned_participant_names"] = []

            for fee_field in ("tax_vnd", "service_fee_vnd", "discount_vnd"):
                val, err = _coerce_strict_int(args.get(fee_field, 0), fee_field, allow_zero=True)
                if err:
                    return f"Validation error: {err}"
                args[fee_field] = val

        return None


class PrerequisiteContactGuard:
    """Prevents hallucinated recipient IDs and premature drafts on ambiguous contacts."""

    name = "prerequisite_contact"

    def check(
        self,
        call: ProposedToolCall,
        state: SessionState,
        user_text: str,
        executed_in_turn: list[dict[str, Any]],
    ) -> str | None:
        if call.name != "create_payment_draft":
            return None

        rid = str(call.arguments.get("recipient_id", "")).strip()
        valid_ids = set(state.seen_contacts.keys()) | set(state.seen_recipient_account_ids)
        if not valid_ids:
            return (
                "PREREQUISITE ERROR: You must call 'find_contacts' first to resolve the recipient "
                "before calling 'create_payment_draft'."
            )
        if rid not in valid_ids:
            return (
                f"HALLUCINATION BLOCKED: recipient_id '{rid}' was not returned by 'find_contacts'. "
                "Call 'find_contacts' and use an exact verified id."
            )

        # If the latest search was ambiguous, check whether the chosen match is clearly disambiguated
        last_search = state.last_contact_search
        if last_search and last_search.get("is_ambiguous"):
            matches = last_search.get("matches", [])
            chosen = next(
                (m for m in matches if m.get("id") == rid or m.get("recipient_account_id") == rid),
                None,
            )
            if chosen:
                full_name = (chosen.get("display_name") or "").lower()
                phone = (chosen.get("phone_number") or "").lower()
                bank = (chosen.get("bank_name") or "").lower()
                text_lower = user_text.lower()
                if full_name not in text_lower and (not phone or phone not in text_lower) and (not bank or bank not in text_lower):
                    names_list = ", ".join(
                        f"{m.get('display_name')} ({m.get('bank_name') or 'MoMo'} - {m.get('phone_number')})"
                        for m in matches
                    )
                    return (
                        f"AMBIGUITY BLOCKED: Multiple contacts matched ({names_list}) and the user did not "
                        "specify which one. Stop and ask the user to choose the exact recipient."
                    )
        return None


class DuplicateWriteGuard:
    """Prevents repeating identical state-mutating drafts within a single turn."""

    name = "duplicate_write"

    def check(
        self,
        call: ProposedToolCall,
        state: SessionState,
        user_text: str,
        executed_in_turn: list[dict[str, Any]],
    ) -> str | None:
        if call.name not in WRITE_TOOLS:
            return None
        key = (call.name, json.dumps(call.arguments, sort_keys=True, ensure_ascii=False))
        for prev in executed_in_turn:
            prev_key = (prev["name"], json.dumps(prev["arguments"], sort_keys=True, ensure_ascii=False))
            if prev_key == key:
                return f"DUPLICATE BLOCKED: '{call.name}' with these exact arguments was already executed in this turn."
        return None


def default_fintech_guards() -> list[Guard]:
    return [
        AllowedToolGuard(),
        FinancialSchemaGuard(),
        PrerequisiteContactGuard(),
        DuplicateWriteGuard(),
    ]
