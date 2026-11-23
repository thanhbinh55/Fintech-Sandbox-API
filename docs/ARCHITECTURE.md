# Fintech Sandbox API - Architecture Documentation

## 1. System Overview

The **Fintech Sandbox API** is an independent, stateful financial execution backend designed for the MoMo Tech Contest 2026. It simulates the financial rails of a modern Vietnamese e-wallet environment to empower an AI Financial Copilot (developed by Developer B).

```
+-------------------------------------------------------------+
|             User / Application Frontend (UI)                |
+-------------------------------------------------------------+
         |                                         ^
         | User Scope (Approve / Execute)          | Verified Result
         v                                         |
+--------------------------+        +--------------------------+
|  Fintech Sandbox API     |<-------|  AI Copilot (Gemini)     |
|  (Developer A)           |        |  (Developer B)           |
+--------------------------+        +--------------------------+
    - Multi-tenant Sessions              - Natural Language
    - Contact Resolution (Ambiguity)     - Tool Selection
    - Payment Intent Lifecycle           - Conversation State
    - Smart Routing Engine (Deterministic)
    - Double-Entry Ledger
    - Exact VND Bill Splitting
```

---

## 2. Core Architectural Pillars

### 2.1 Multi-Tenant Logical Session Isolation
Every financial record (`users`, `accounts`, `contacts`, `payment_intents`, `transactions`, `split_bills`, `audit_events`) is partitioned by `demo_session_id`. Tokens are cryptographically signed HMAC-SHA256 bearer tokens containing `session_id`, `user_id`, and `scope`. Cross-session lookups fail with HTTP 404 or HTTP 403.

### 2.2 Strict Payment Lifecycle State Machine
Financial state transitions are monotonic and explicit:
`DRAFT` -> `QUOTED` -> `AWAITING_APPROVAL` -> `APPROVED` -> `PROCESSING` -> `SIMULATED_SUCCESS` or `FAILED`.
- Gated Approval: Execution requires an active `PaymentApproval` snapshot matching the exact `intent.version`.
- Snapshot Locking: Prevents modification of recipient, amount, or fees after user approval.

### 2.3 Double-Entry Ledger and Integer VND Accounting
- All amounts are 64-bit non-negative integers (`BigInteger`). Floating-point arithmetic is prohibited.
- Transfers write atomic `DEBIT` and `CREDIT` entries in a single database transaction.
- When promotional discounts apply, the user's account is debited `amount_debited_vnd`, the recipient account is credited `amount_vnd`, and the discount is funded by the `INTERNAL_SETTLEMENT` clearing account, ensuring:
  $$\sum \text{Debits} = \sum \text{Credits}$$

### 2.4 Deterministic Smart Routing Engine
Quotes evaluate fees, immediate discounts, and delayed cashback:
$$\text{effective\_cost\_vnd} = \text{amount\_debited\_vnd} - \text{estimated\_reward\_vnd}$$
$$\text{amount\_debited\_vnd} = \text{amount\_vnd} + \text{fee\_vnd} - \text{immediate\_discount\_vnd}$$
Deterministic tie-breaking:
1. `eligible` (True over False)
2. `effective_cost_vnd` (Lowest first)
3. `amount_debited_vnd` (Lowest first)
4. `fee_vnd` (Lowest first)
5. Source priority: `EWALLET` > `SIMULATED_BANK` > `SIMULATED_CARD`

### 2.5 Exact Integer VND Group Bill Splitting
- Shared and itemized allocations distribute subtotals using integer division:
  $$\text{base\_share} = \text{item\_total} // N, \quad \text{remainder} = \text{item\_total} \% N$$
- Remainder is distributed deterministically 1 VND per participant ordered by ID.
- Tax, service charges, and discounts are distributed proportionally.
- Invariants:
  $$\sum \text{participant\_shares} = \text{bill\_total}$$
  $$\sum \text{collected\_amounts} \le \text{collection\_requests}$$

