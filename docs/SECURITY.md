# Fintech Sandbox API - Security & Permission Architecture

## 1. Scoped Role-Based Authentication

Requests to the API authenticate via HTTP Bearer token:
`Authorization: Bearer <token>`

The system enforces three permission tiers:

| Scope | Permitted Actions | Prohibited Actions | Intended Consumer |
|---|---|---|---|
| `agent` | Read contacts, check sources/balances, create drafts, calculate routing quotes, query split bills, read transaction history | Approve payment, execute payment, reset session, simulate deposits | AI Financial Copilot Backend (Dev B) |
| `user` | All agent actions + approve payment quotes, execute transfers, settle collection requests | Session creation with arbitrary seeds, direct deposit simulation | Human-in-the-loop Frontend (User actions) |
| `demo-control` | Create demo sessions, reset sessions, simulate incoming bank top-ups, read audit logs | Ordinary consumer payments | Test automation / Demo orchestrator |

---

## 2. Human-In-The-Loop Financial Safety Invariants

1. **AI Agent Cannot Transfer Funds:**
   - Any attempt by the `agent` token to invoke `POST /v1/payment-intents/{id}/approve` or `POST /v1/payment-intents/{id}/execute` is rejected with `HTTP 403 FORBIDDEN` (`FORBIDDEN`).
2. **Immutable Approval Snapshot:**
   - When a user approves a quote, the backend captures an exact snapshot of:
     - `amount_vnd`, `fee_vnd`, `discount_vnd`, `amount_debited_vnd`
     - `source_account_id`, `recipient_account_id`
     - `intent_version`
   - If the intent draft is modified after approval (incrementing `version`), the existing approval is invalidated.
3. **Idempotency Protection:**
   - Mutating execution endpoints accept an `idempotency_key`. Repeating a request with the same key returns the existing transaction result without duplicating debits or ledger writes.
4. **Zero Live Credential Exposure:**
   - The sandbox contains fictional financial records only. No real bank PINs, OTPs, or passwords are stored or requested.
