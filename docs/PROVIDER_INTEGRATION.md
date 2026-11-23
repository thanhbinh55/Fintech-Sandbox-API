# Provider-Based Integration Architecture & Technical Audit

**Project:** Fintech Sandbox API (MoMo Tech Contest 2026 Simulation)  
**Date:** 2026-11-24  
**Document Version:** 1.0.0

---

## 1. External API Audit & Integration Inventory

Prior to this architectural extension, an audit of the codebase was conducted to categorize integrations:

| Capability | Integration Status | Technology / Details |
|---|---|---|
| **Core Account & Transfers** | Fully Functional Internal | Double-entry ledger (`LedgerService`), SQLite & PostgreSQL persistence. Atomic balance mutation. |
| **Smart Payment Routing** | Fully Functional Internal | Deterministic ranking engine evaluating fees, discounts, and cashback caps. |
| **Group Bill Splitting** | Fully Functional Internal | Integer VND exact math with deterministic remainder allocation. |
| **SePay Payment Gateway** | Verified Adapter with Safe Fallback | Verified official endpoints (`pay-sandbox.sepay.vn`, `pgapi-sandbox.sepay.vn`). Mocked integration tests & live smoke tests when credentials exist. |
| **VietQR NAPAS EMVCo QR** | Fully Functional Standard Adapter | Local EMVCo string generation with CRC16-CCITT checksum and `img.vietqr.io` quick link image URLs. Clearly separated from sandbox settlement. |

---

## 2. Payment Provider Architecture (`PaymentProvider`)

All payment operations go through the `PaymentProvider` interface defined in `app/providers/base.py`:

```
                       +-------------------------------+
                       |   PaymentService.execute()    |
                       +-------------------------------+
                                       |
                                       v
                       +-------------------------------+
                       |       get_payment_provider()  |
                       +-------------------------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
+------------------------------------+  +------------------------------------+
|     InternalSimulationProvider     |  |       SePaySandboxProvider         |
|  (Default - Mandatory, 100% Local) |  |   (Optional Sandbox Gateway)       |
+------------------------------------+  +------------------------------------+
                   |                                       |
                   |                                       | If credentials missing
                   |                                       | or network failure
                   |                                       v
                   +---------------------------< Safe Fallback to Internal
```

### 2.1 InternalSimulationProvider (Mandatory)
- **Role:** Default primary provider. Operates 100% locally with zero external network dependencies.
- **Financial Invariant:** Executes double-entry atomic transactions on the database, deducting debited funds and crediting recipient/clearing accounts.
- **Availability:** Always available (`is_available() == True`).

### 2.2 SePaySandboxProvider (Optional External Gateway)
- **Verified Official Endpoints:**
  - Checkout Init: `https://pay-sandbox.sepay.vn/v1/checkout/init`
  - REST API Lookup: `https://pgapi-sandbox.sepay.vn`
- **Authentication:** HTTP Basic Authentication using `SEPAY_MERCHANT_ID:SEPAY_SECRET_KEY` encoded in Base64.
- **Safe Fallback Guarantees (Requirements 5 & 6):**
  1. **Financial Integrity:** Always executes internal ledger updates and checks account balance/credit limits prior to attempting any external gateway communication.
  2. **Unconfigured Fallback:** If `SEPAY_MERCHANT_ID` or `SEPAY_SECRET_KEY` are not set in the environment, the provider logs a structured notice and immediately executes the transaction via internal simulation, setting `fallback_used: true`.
  3. **Fault Tolerance:** If SePay returns HTTP 5xx, 4xx, network timeout, or connection dropped, the provider catches the error, logs a warning, and executes the fallback simulation. The user demo never crashes or gets blocked.
- **Unsupported / Unverified Features:**
  - Real-time incoming webhook / IPN listener requires a publicly reachable HTTPS domain (e.g., ngrok or production domain) which is not active in default local development environments.

---

## 3. QR Provider Architecture (`QRProvider`)

Collection requests in group bill splitting utilize the `QRProvider` interface:

### 3.1 InternalSandboxQRProvider (Mandatory)
- **Format:** `SANDBOX_VND_PAYMENT:split_bill_id={split_id}&request_id={request_id}&amount={share}&recipient={name}`
- **Payment Link:** `https://sandbox.wallet.local/pay/split/{request_id}`
- **Role:** Internal simulation format designed for sandbox tests and internal demo settlement.

### 3.2 VietQRProvider (Optional Standard Rail)
- **Standard:** NAPAS EMVCo QR Code Specification for Payment Systems (Merchant-Presented Mode).
- **EMVCo Structure Implemented:**
  - Tag `00`: Payload Format Indicator (`"01"`)
  - Tag `01`: Point of Initiation Method (`"12"` - Dynamic with amount)
  - Tag `38`: NAPAS Beneficiary Sub-TLV (GUID `A000000727`, Bank BIN, Account Number)
  - Tag `52`: MCC (`"0000"`)
  - Tag `53`: Currency code (`"704"` - VND)
  - Tag `54`: Transaction amount (integer VND string)
  - Tag `58`: Country code (`"VN"`)
  - Tag `59`: Beneficiary Name
  - Tag `60`: City (`"HCM"`)
  - Tag `62`: Additional Data Template (`08` - Narrative reference)
  - Tag `63`: CRC16-CCITT checksum footer (Polynomial `0x1021`, Initial `0xFFFF`)
- **Quick Link Image URL:** `https://img.vietqr.io/image/{bank_bin}-{account_no}-{template}.png?amount={amount}&addInfo={narrative}&accountName={name}`
- **Settlement Boundary:** Clearly tagged with `is_external_payment_rail: true` and simulation disclaimer:
  > *VIETQR STANDARD DISPLAY QR: Generated per NAPAS EMVCo QR specifications. This external QR is for mobile banking display and does NOT auto-settle the sandbox ledger without an explicit simulated settlement trigger.*

---

## 4. Environment Configuration Matrix

| Variable | Default | Allowed Values | Description |
|---|---|---|---|
| `PAYMENT_PROVIDER` | `internal` | `internal`, `sepay` | Active payment execution provider |
| `QR_PROVIDER` | `internal` | `internal`, `vietqr` | Active collection QR generator |
| `SEPAY_MERCHANT_ID` | `None` | String | Merchant ID from SePay Sandbox |
| `SEPAY_SECRET_KEY` | `None` | String | Secret Key from SePay Sandbox |
| `SEPAY_BASE_URL` | `https://pgapi-sandbox.sepay.vn` | URL | SePay REST API endpoint |
| `SEPAY_CHECKOUT_URL` | `https://pay-sandbox.sepay.vn/v1/checkout/init` | URL | SePay Checkout Init endpoint |
| `SEPAY_FALLBACK_TO_SIMULATION` | `true` | `true`, `false` | Fall back to simulation on SePay failure |
| `VIETQR_DEFAULT_BANK_BIN` | `970436` | 6-digit BIN | Default receiving bank BIN (Vietcombank) |
| `VIETQR_DEFAULT_TEMPLATE` | `compact2` | `compact`, `compact2`, `print` | VietQR layout template |

---

## 5. Developer B Contract Compatibility

The provider abstraction was introduced without changing any endpoint paths, request bodies, or required response fields:
- `POST /v1/payment-intents/{id}/execute` returns the exact same `PaymentExecuteResponse`, with optional non-breaking provider fields (`provider_name`, `provider_reference_id`, `fallback_used`).
- `GET /v1/split-bills/{id}/requests/{req_id}/qr` returns `qr_payload`, `sandbox_payment_link`, and adds `provider_name` and `is_external_payment_rail`.
- Developer B's Python SDK client (`FintechSandboxClient`) and tool declarations require zero modifications.

