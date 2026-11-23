# Fintech Sandbox API - Demo Scenarios

This document details the reproducible scenarios seeded into every demo session.

---

## Scenario A — Normal Payment & Ambiguity Handling

### Initial State
- Primary User: **An** (`0901234567`)
- Accounts:
  - Ví MoMo Sandbox: `1,500,000 VND`
  - Vietcombank Demo: `5,000,000 VND`
  - Techcombank Visa Demo: `2,000,000 VND` available credit
- Contacts:
  - **Nguyễn Minh** (`0912345678` - Ví MoMo)
  - **Trần Minh** (`0923456789` - BIDV)
  - **Lan** (`0934567890` - Ví MoMo)

### Workflow A.1: Ambiguity Handling
1. User prompt: *"Chuyển cho Minh 150 nghìn"*
2. AI calls `find_contacts("Minh")`.
3. Backend returns `is_ambiguous: True`, 2 matches: Nguyễn Minh and Trần Minh.
4. AI clarifies: *"Tìm thấy 2 người nhận là Nguyễn Minh và Trần Minh. Bạn muốn chuyển cho ai?"*

### Workflow A.2: Payment Execution
1. User clarifies: *"Chuyển cho Nguyễn Minh"*
2. AI calls `create_payment_draft(recipient_id, 150000, "Tiền ăn tối")` -> `status: DRAFT`.
3. AI calls `get_payment_quotes(intent_id)` -> ranked quotes generated (`QUOTED`).
4. User reviews quotes on UI and clicks **Xác nhận**.
5. Frontend calls `approve` and `execute` with user token.
6. Result: An's Ví MoMo balance decreases to `1,350,000 VND`, Nguyễn Minh's balance increases from `500,000 VND` to `650,000 VND`.

---

## Scenario B — Smart Payment Routing

### Scenario Setup
User prompt: *"Thanh toán 150.000đ bằng nguồn tiền nào có lợi nhất?"*
Available Offers:
1. **VCB_CASHBACK_5K**: Hoàn tiền 5,000 VND cho giao dịch từ 100,000 VND qua Vietcombank.
2. **TCB_DISCOUNT_10PCT**: Giảm 10% tối đa 20,000 VND cho thẻ Techcombank (nhưng có phí giao dịch thẻ 1,000 VND).
3. **Ví MoMo**: Không phí, không khuyến mãi.

### Calculated Ranking:
| Source | Phí (Fee) | Giảm giá tức thì | Số tiền trừ ngay | Hoàn tiền dự kiến | Chi phí hiệu quả | Xếp hạng |
|---|---|---|---|---|---|---|
| **Techcombank Visa** | 1,000đ | 15,000đ | 136,000đ | 0đ | **136,000đ** | **#1 (Recommended)** |
| **Vietcombank** | 0đ | 0đ | 150,000đ | 5,000đ | **145,000đ** | **#2** |
| **Ví MoMo** | 0đ | 0đ | 150,000đ | 0đ | **150,000đ** | **#3** |

Backend explanation: *"Khuyên dùng Techcombank Visa vì có chi phí hiệu quả thấp nhất (136,000đ) nhờ ưu đãi giảm giá 15,000đ."*

---

## Scenario C — Group Bill Splitting

### Bill Breakdown: 180,000 VND
- 3 phần cơm x 50,000 VND = `150,000 VND` (chia đều cho An, Bình, Cường)
- 1 phần nước cam = `30,000 VND` (An uống một mình)
- Payer: **An**

### Calculation Output:
- **An:** 50,000đ (cơm) + 30,000đ (nước) = **80,000đ** (Payer - Đã trả trước, còn nợ 0đ)
- **Bình:** 50,000đ (cơm) = **50,000đ** (Collection request tạo với QR sandbox)
- **Cường:** 50,000đ (cơm) = **50,000đ** (Collection request tạo với QR sandbox)
- Invariant: $80,000 + 50,000 + 50,000 = 180,000$ VND.

When Bình pays via sandbox link:
- Total collected updates from 80,000đ to 130,000đ.
- Remaining to collect: 50,000đ (Cường).
- Bill status: `ACTIVE`. When Cường pays, status updates to `SETTLED`.

---

## Edge Case Scenarios

- **Insufficient Funds (E2E-05):** Attempting to spend 50,000,000 VND causes all quotes to be marked `eligible: False`, rejecting approval with `INSUFFICIENT_FUNDS`.
- **Duplicate Execution (E2E-06):** Retrying `execute` with the same `idempotency_key` safely returns the cached transaction without double-debiting.
- **Cross-Session Isolation (Security):** User in Session 1 accessing resources from Session 2 receives HTTP 404 or 403.
- **Session Reset (E2E-07):** Calling `POST /v1/demo/reset` instantly restores all accounts, contacts, and balances to the initial seed state.
