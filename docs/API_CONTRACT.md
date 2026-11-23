# Fintech Sandbox API - Contract Specification (v1)

Base URL: `/v1`  
Specification Version: `1.0.0`  
Currency: All monetary values are non-negative 64-bit integers in Vietnamese Đồng (`VND`). Floating points are rejected.

---

## Standard Response Schemas

### 1. Success Envelope
```json
{
  "success": true,
  "data": { ... },
  "request_id": "req_01j7..."
}
```

### 2. Error Envelope
```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Source account available balance (50000 VND) is less than total debit amount (150000 VND).",
    "details": {
      "source_account_id": "acc_01...",
      "available_balance_vnd": 50000,
      "required_amount_vnd": 150000
    }
  },
  "request_id": "req_01j7..."
}
```

### Standard Error Codes
| Code | HTTP Status | Description |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing, malformed, or expired token |
| `FORBIDDEN` | 403 | Insufficient permission scope (e.g., agent calling execution endpoint) |
| `RESOURCE_NOT_FOUND` | 404 | Entity not found or not in caller's demo session |
| `VALIDATION_ERROR` | 422 | Schema validation failure, negative amount, etc. |
| `INSUFFICIENT_FUNDS` | 400 | Account balance or credit limit inadequate |
| `AMBIGUOUS_RECIPIENT` | 400 | Multiple contacts match query |
| `CONTACT_NOT_FOUND` | 404 | No contact found matching criteria |
| `QUOTE_EXPIRED` | 400 | Payment quote expired prior to approval/execution |
| `INVALID_STATE` | 400 | Action invalid for current payment intent state |
| `SOURCE_NOT_ELIGIBLE` | 400 | Payment source not eligible for payment |
| `DUPLICATE_REQUEST` | 409 | Idempotency conflict with differing payload |
| `CROSS_SESSION_ACCESS_DENIED` | 403 | Attempt to reference entity from another session |

---

## Authentication & Authorization Scopes

Requests authenticate via `Authorization: Bearer <session_token>`.
Tokens encode:
- `session_id`: Unique isolated demo environment
- `user_id`: Target primary user or participant
- `scope`:
  - `user`: Initiates payment drafts, approves quotes, executes payments, manages bill splits.
  - `agent`: Read-only queries, contact searches, quote calculations, draft creations. **Forbidden from calling `/approve`, `/execute`, or `/demo/reset`.**
  - `demo-control`: Administrative management (session creation, full reset, incoming payment simulation).

---

## Endpoint Summary

### 1. Demo & Session
- `POST /v1/demo/sessions` (demo-control/public): Create new seeded demo session.
- `GET /v1/demo/sessions/me` (any scope): Get active session metadata.
- `POST /v1/demo/reset` (demo-control or user): Reset caller's session to seed state.
- `GET /health`: Health status.
- `GET /ready`: Readiness probe (checks DB connectivity).

### 2. Accounts & Sources
- `GET /v1/me/accounts` (user, agent): List user's simulated accounts & balances.
- `GET /v1/payment-sources` (user, agent): List available payment sources with available funds/credit.
- `GET /v1/payment-sources/{source_id}` (user, agent): Get details of a single source.
- `GET /v1/transactions` (user, agent): Paginated transaction history.

### 3. Contacts & Recipient Resolution
- `GET /v1/contacts?q={query}` (user, agent): Search contacts by name, phone, or alias. Returns ambiguity flag.
- `GET /v1/contacts/{contact_id}` (user, agent): Get single contact.
- `POST /v1/contacts` (user): Add a new contact.
- `PATCH /v1/contacts/{contact_id}` (user): Update contact.

### 4. Payment Intent Lifecycle & Human-In-The-Loop Approval
- `POST /v1/payment-intents` (user, agent): Create payment draft (`DRAFT`).
- `GET /v1/payment-intents/{intent_id}` (user, agent): Retrieve payment intent details.
- `POST /v1/payment-intents/{intent_id}/quotes` (user, agent): Generate ranked quotes via routing engine (`QUOTED`).
- `POST /v1/payment-intents/{intent_id}/approve` (**user ONLY**): Approve quote, snapshotting intent & quote (`APPROVED`).
- `POST /v1/payment-intents/{intent_id}/execute` (**user ONLY**): Atomically verify snapshot & execute transfer (`SIMULATED_SUCCESS` or `FAILED`).
- `GET /v1/payment-intents/{intent_id}/status` (user, agent): Check status.

### 5. Smart Routing & Offers
- `GET /v1/offers` (user, agent): List available simulated offers/promotions.
- `GET /v1/offers/{offer_id}` (user, agent): Get single offer.

### 6. Bill Splitting
- `POST /v1/split-bills` (user, agent): Create itemized split bill with participants and item assignments.
- `GET /v1/split-bills/{split_id}` (user, agent): Get split bill details, item breakdown, and participant shares.
- `POST /v1/split-bills/{split_id}/requests` (user): Generate collection requests for participants.
- `GET /v1/split-bills/{split_id}/status` (user, agent): Get live settlement and collection summary.
- `GET /v1/split-bills/{split_id}/requests/{request_id}/qr` (user, agent): Get simulated sandbox payment QR code and payment link.
- `POST /v1/split-bills/{split_id}/requests/{request_id}/settle` (user): Simulate participant paying their share.

### 7. Simulation & Audit (demo-control scope only)
- `POST /v1/demo/simulate-incoming`: Simulate external deposit into user wallet/bank.
- `POST /v1/demo/simulate-failure`: Force simulated failure on next payment.
- `GET /v1/events`: Query audit event log.
