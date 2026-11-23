# Integration Handoff Guide for Developer B (AI Copilot Engineer)

**Project:** Fintech Sandbox API (MoMo Tech Contest 2026 Simulation)  
**Author:** Developer A (Principal Backend Engineer & Fintech System Architect)  
**Recipient:** Developer B (AI Agent Orchestration & Copilot Developer)  
**Date:** 2026-11-24  
**Version:** 1.0.0 (Production / Integration Ready)

---

## 1. Sandbox Overview

The **Fintech Sandbox API** is an independent, stateful simulation backend of a modern Vietnamese e-wallet environment (MoMo-style). It provides:
- Deterministic contact resolution and ambiguous recipient detection.
- Complete payment intent lifecycle with human-in-the-loop snapshot approval.
- Deterministic Smart Payment Routing ranking sources by fees, instant discounts, and cashback.
- Exact integer VND group bill splitting with zero floating point errors and remainder round-off handling.
- Double-entry atomic ledger accounting.
- Multi-tenant isolated demo environments with reproducible seeding and zero cross-session data leakage.

> [!WARNING]
> **SIMULATION ONLY:** This sandbox operates entirely on fictional test balances and simulated rails. It does not connect to real banking networks or live MoMo services.

---

## 2. Architecture Summary

- **Framework:** FastAPI with Python 3.12, Pydantic v2 schemas.
- **ORM & Database:** SQLAlchemy 2.x, Alembic migrations, PostgreSQL (production/Docker) & SQLite (local fallback).
- **Currencies & Precision:** Strictly 64-bit non-negative integer VND (`BigInteger`). Floats are rejected.
- **State Machine:** Monotonic states (`DRAFT` -> `QUOTED` -> `AWAITING_APPROVAL` -> `APPROVED` -> `PROCESSING` -> `SIMULATED_SUCCESS`).
- **Security:** Scoped HMAC-SHA256 bearer tokens separating `agent` (read/draft only) from `user` (human approval/execution) and `demo-control` (session lifecycle).
- **Provider Architecture:** Extensible adapters for Payment (`InternalSimulationProvider`, `SePaySandboxProvider`) and QR (`InternalSandboxQRProvider`, `VietQRProvider`) configured via environment variables with zero breaking changes to existing contracts. See [docs/PROVIDER_INTEGRATION.md](file:///Users/ngovietthanhbinh/Project/Fintech-Sandbox-API/docs/PROVIDER_INTEGRATION.md).

---

## 3. How to Start the Service

### Option 1: Local Virtual Environment with UV (Recommended for Development)
```bash
# Activate existing virtual environment
source .venv/bin/activate

# Run database migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: Docker Compose (Full Stack with PostgreSQL)
```bash
docker compose up --build -d
```

---

## 4. Base URL & OpenAPI Specification

- **Base URL:** `http://localhost:8000/v1`
- **Swagger UI Interactive Docs:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI 3.1 JSON Specification:** `http://localhost:8000/openapi.json` (also stored at repo root [openapi.json](file:///Users/ngovietthanhbinh/Project/Fintech-Sandbox-API/openapi.json))

---

## 5. Authentication & Scoped Credentials

All `/v1` endpoints require an HTTP Bearer header:
```http
Authorization: Bearer <token>
```

When you create a demo session via `POST /v1/demo/sessions`, the API returns three pre-scoped credentials:
1. `agent_token`: Use this in your Gemini tool caller backend. It can read contacts, quotes, and create draft payment intents, but is **strictly blocked (HTTP 403)** from executing or approving payments.
2. `user_token`: Used by the application frontend when the human user taps "Xác nhận thanh toán" to approve and execute transactions.
3. `demo_control_token`: Used for resetting the session or simulating external top-up deposits.

---

## 6. How to Create a Demo Session

### Request
```http
POST /v1/demo/sessions HTTP/1.1
Content-Type: application/json

{
  "scenario": "scenario_a",
  "display_name": "MoMo Contest Demo 01"
}
```

### Response
```json
{
  "success": true,
  "data": {
    "id": "2c02d41e-2cce-47af-9591-161dd5149f5c",
    "display_name": "MoMo Contest Demo 01",
    "seed_scenario": "scenario_a",
    "status": "ACTIVE",
    "created_at": "2026-11-24T00:00:00Z",
    "expires_at": "2026-11-25T00:00:00Z",
    "credentials": {
      "user_token": "eyJzZXNzaW9uX2lkIjoi...",
      "agent_token": "eyJzZXNzaW9uX2lkIjoi...",
      "demo_control_token": "eyJzZXNzaW9uX2lkIjoi..."
    }
  },
  "request_id": "req_01j7..."
}
```

---

## 7. List of Agent-Callable Tools

Register ONLY these tools in the Gemini function calling registry:

| Tool / SDK Function | HTTP Endpoint | Description |
|---|---|---|
| `find_contacts(query)` | `GET /v1/contacts?q={query}` | Search contacts with automatic ambiguity detection |
| `get_contact(contact_id)` | `GET /v1/contacts/{id}` | Get single contact details |
| `get_payment_sources()` | `GET /v1/payment-sources` | List available user wallets, banks, and cards with balances |
| `get_account_snapshot()` | `GET /v1/me/accounts` | Complete snapshot of accounts and credit limits |
| `create_payment_draft(...)` | `POST /v1/payment-intents` | Create a transfer draft (`DRAFT`) |
| `get_payment_quotes(intent_id)` | `POST /v1/payment-intents/{id}/quotes` | Calculate deterministic fee, discount, and cashback quotes |
| `get_payment_intent(intent_id)` | `GET /v1/payment-intents/{id}` | Check intent status and quotes |
| `get_transaction_history(...)` | `GET /v1/transactions` | Query past transactions and double-entry ledger |
| `create_split_bill(...)` | `POST /v1/split-bills` | Create exact integer VND group bill split |
| `get_split_bill(split_id)` | `GET /v1/split-bills/{id}` | Get split bill details and participant shares |
| `get_split_status(split_id)` | `GET /v1/split-bills/{id}/status` | Check live collection and settlement status |

> [!CAUTION]
> **DO NOT EXPOSE TO LLM:**
> - `POST /v1/payment-intents/{id}/approve`
> - `POST /v1/payment-intents/{id}/execute`
> - `POST /v1/demo/reset`
> - `POST /v1/demo/simulate-incoming`
> These must only be triggered by the user via frontend UI actions.

---

## 8. Python SDK Usage

Install or import directly from `sdk/python/fintech_sandbox_client`:

```python
import asyncio
from sdk.python.fintech_sandbox_client import FintechSandboxClient

async def main():
    client = FintechSandboxClient(
        base_url="http://localhost:8000/v1",
        token="<YOUR_AGENT_TOKEN>"
    )

    # Search contacts
    result = await client.find_contacts("Minh")
    if result.is_ambiguous:
        print(result.clarification_message)
        # Display candidates to user: result.matches

    # Create payment draft
    draft = await client.create_payment_draft(
        recipient_id=result.matches[0].recipient_account_id,
        amount_vnd=150000,
        note="Tiền ăn trưa"
    )

    # Get ranked quotes
    quotes = await client.get_payment_quotes(draft.id)
    for q in quotes:
        print(f"Nguồn: {q.source_display_name}, Chi phí hiệu quả: {q.effective_cost_vnd:,}đ")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 9. Seed User & Account Details (Scenario A)

- **Primary User:** An (`0901234567`)
- **Simulated Payment Sources:**
  1. `Ví MoMo Sandbox` (EWALLET): `1,500,000 VND` (0 fee, instant)
  2. `Vietcombank Demo` (SIMULATED_BANK): `5,000,000 VND` (0 fee, 5k cashback for transfers >= 100k)
  3. `Techcombank Visa Demo` (SIMULATED_CARD): `2,000,000 VND` available credit (1k fee, 10% discount max 20k)
- **Saved Contacts:**
  - `Nguyễn Minh` (`0912345678` - Ví MoMo)
  - `Trần Minh` (`0923456789` - BIDV)
  - `Lan` (`0934567890` - Ví MoMo)

---

## 10. Standard Error Codes Reference

| Error Code | HTTP Status | Description | Action for AI Copilot |
|---|---|---|---|
| `AMBIGUOUS_RECIPIENT` | 400 | Multiple contacts match query | Ask user which specific recipient they mean |
| `CONTACT_NOT_FOUND` | 404 | No contact matched | Ask user for recipient phone number or account |
| `INSUFFICIENT_FUNDS` | 400 | Balance/credit is insufficient | Suggest switching to another payment source |
| `QUOTE_EXPIRED` | 400 | Quote expired (>15 min) | Call `get_payment_quotes` again for fresh rates |
| `INVALID_STATE` | 400 | Invalid state transition | Re-check payment intent status |
| `FORBIDDEN` | 403 | Scope permission denied | Tell user approval requires human action |

---

## 11. Testing and Verification Commands

Verify everything locally anytime:
```bash
source .venv/bin/activate

# 1. Run full automated test suite (28 tests across unit, integration, security, integrity, e2e)
pytest -v

# 2. Run code coverage
coverage run -m pytest && coverage report -m

# 3. Run quick smoke test
python -m scripts.smoke_test

# 4. Re-export OpenAPI JSON schema
python -m scripts.export_openapi
```

