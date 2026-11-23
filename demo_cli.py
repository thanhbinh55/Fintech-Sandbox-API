"""Interactive Terminal Demo for Fintech Sandbox API.

Allows users to test all features (Chat-to-Pay, Smart Routing, Bill Split)
in plain Vietnamese without needing to understand or touch Swagger UI.
"""
import sys
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def print_banner(text: str):
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def main():
    print_banner("CHÀO MỪNG BẠN ĐẾN VỚI FINTECH SANDBOX (MOMO TECH CONTEST 2026)")
    print("Hệ thống đang tự động khởi tạo môi trường thử nghiệm với số dư giả lập...")

    # 1. Initialize demo session
    res = client.post("/v1/demo/sessions", json={"scenario": "scenario_a", "display_name": "Terminal Demo"})
    if res.status_code != 200:
        print("❌ Lỗi khởi tạo phiên:", res.text)
        return

    data = res.json()["data"]
    session_id = data["id"]
    agent_token = data["credentials"]["agent_token"]
    user_token = data["credentials"]["user_token"]

    agent_headers = {"Authorization": f"Bearer {agent_token}"}
    user_headers = {"Authorization": f"Bearer {user_token}"}

    print(f"✅ Đã tạo phiên thành công! (Mã phiên: {session_id[:8]}...)")

    while True:
        print("\n--- BẠN MUỐN THỬ TÍNH NĂNG NÀO? ---")
        print("1. Chuyển tiền qua câu nói (Chat-to-Pay & Xử lý trùng tên)")
        print("2. Tối ưu nguồn tiền thanh toán (Smart Routing: Thẻ / Ví / Ngân hàng)")
        print("3. Chia hóa đơn ăn uống nhóm (Bill Splitting & Tạo mã QR)")
        print("4. Xem số dư các ví/thẻ và lịch sử giao dịch")
        print("5. Khôi phục số dư ban đầu (Reset demo)")
        print("0. Thoát")

        choice = input("\n👉 Nhập lựa chọn (0-5): ").strip()

        if choice == "1":
            print_banner("TÍNH NĂNG 1: CHUYỂN TIỀN TỰ NHIÊN (CHAT-TO-PAY)")
            query = input("Nhập tên người bạn muốn chuyển (thử gõ 'Minh' hoặc 'Lan'): ").strip() or "Minh"
            print(f"\n🔍 Bước 1: AI tìm kiếm trong danh bạ với từ khóa '{query}'...")

            contact_res = client.get(f"/v1/contacts?q={query}", headers=agent_headers).json()["data"]

            if contact_res["is_ambiguous"]:
                print(f"⚠️ {contact_res['clarification_message']}")
                print("Danh sách người nhận tìm thấy:")
                for idx, c in enumerate(contact_res["matches"], 1):
                    print(f"   [{idx}] {c['display_name']} ({c['alias'] or c['phone_number']}) - {c['bank_name']}")

                sel = input("👉 Bạn chọn chuyển cho ai? (Nhập 1 hoặc 2): ").strip()
                sel_idx = int(sel) - 1 if sel in ("1", "2") else 0
                chosen_contact = contact_res["matches"][sel_idx]
            elif len(contact_res["matches"]) > 0:
                chosen_contact = contact_res["matches"][0]
            else:
                print(f"❌ Không tìm thấy ai tên '{query}'!")
                continue

            print(f"🎯 Đã chọn: {chosen_contact['display_name']} (Tài khoản: {chosen_contact['recipient_account_id']})")

            amount_str = input("👉 Nhập số tiền muốn chuyển (VND, mặc định 150000): ").strip() or "150000"
            amount = int(amount_str)
            note = input("👉 Lời nhắn (mặc định: 'Tien an toi'): ").strip() or "Tien an toi"

            print("\n📝 Bước 2: AI tạo bản nháp giao dịch...")
            draft = client.post(
                "/v1/payment-intents",
                json={"recipient_account_id": chosen_contact["recipient_account_id"], "amount_vnd": amount, "description": note},
                headers=agent_headers,
            ).json()["data"]
            print(f"   Bản nháp đã tạo (Trạng thái: {draft['status']})")

            print("\n💡 Bước 3: AI phân tích và xếp hạng nguồn tiền tốt nhất...")
            quotes = client.post(f"/v1/payment-intents/{draft['id']}/quotes", headers=agent_headers).json()["data"]["quotes"]
            rec_quote = next((q for q in quotes if q["recommended"]), quotes[0])

            print(f"   => AI khuyên dùng: {rec_quote['source_display_name']}")
            print(f"      - Số tiền chuyển: {amount:,}đ")
            print(f"      - Phí giao dịch:  {rec_quote['fee_vnd']:,}đ")
            print(f"      - Giảm giá ngay:  {rec_quote['immediate_discount_vnd']:,}đ")
            print(f"      - Hoàn tiền sau:  {rec_quote['estimated_reward_vnd']:,}đ")
            print(f"      - Thực tế trả:    {rec_quote['effective_cost_vnd']:,}đ")

            confirm = input("\n👤 BƯỚC DUYỆT (Người dùng): Bạn có đồng ý thanh toán không? (c/k): ").strip().lower()
            if confirm in ("c", "y", "dong y", ""):
                print("🔒 Đang duyệt giao dịch (User Scope)...")
                client.post(f"/v1/payment-intents/{draft['id']}/approve", json={"quote_id": rec_quote["id"]}, headers=user_headers)

                print("⚡ Đang thực thi chuyển tiền trên sổ kép (Ledger)...")
                exec_res = client.post(f"/v1/payment-intents/{draft['id']}/execute", json={}, headers=user_headers).json()["data"]

                print("\n🎉 THÀNH CÔNG RỰC RỠ!")
                print(f"   Mã giao dịch: {exec_res['transaction_id']}")
                print(f"   Số tiền đã trừ: {exec_res['amount_debited_vnd']:,} VND")
                print(f"   Người nhận: {chosen_contact['display_name']}")
            else:
                print("❌ Bạn đã hủy giao dịch. Tiền trong ví được giữ nguyên.")

        elif choice == "2":
            print_banner("TÍNH NĂNG 2: SMART ROUTING (TỐI ƯU HÓA NGUỒN TIỀN)")
            amount = int(input("👉 Nhập số tiền cần thanh toán (thử 200000): ").strip() or "200000")

            # Get candidate recipient
            lan = client.get("/v1/contacts?q=Lan", headers=agent_headers).json()["data"]["matches"][0]
            draft = client.post(
                "/v1/payment-intents",
                json={"recipient_account_id": lan["recipient_account_id"], "amount_vnd": amount, "description": "So sanh nguon tien"},
                headers=agent_headers,
            ).json()["data"]

            res = client.post(f"/v1/payment-intents/{draft['id']}/quotes", headers=agent_headers).json()["data"]
            quotes = res["quotes"]

            print(f"\nBẢNG SO SÁNH CÁC NGUỒN TIỀN CHO SỐ TIỀN {amount:,} VND:")
            print(f"{'Nguồn tiền':<28} | {'Số dư':<12} | {'Phí':<8} | {'Giảm':<8} | {'Hoàn':<8} | {'Chi phí thực'}")
            print("-" * 80)
            for q in quotes:
                star = "⭐ KHUYÊN DÙNG" if q["recommended"] else ""
                print(f"{q['source_display_name']:<28} | {'Khả dụng':<12} | {q['fee_vnd']:<8,} | {q['immediate_discount_vnd']:<8,} | {q['estimated_reward_vnd']:<8,} | {q['effective_cost_vnd']:,}đ {star}")

            print(f"\n💡 Tóm tắt gợi ý của AI: {res['recommendation_summary']}")

        elif choice == "3":
            print_banner("TÍNH NĂNG 3: CHIA TIỀN HÓA ĐƠN ĂN UỐNG (BILL SPLITTING)")
            print("Giả lập hóa đơn 180,000 VND:")
            print(" - 3 suất Cơm sườn (50,000đ/suất) = 150,000đ (An, Bình, Cường ăn chung)")
            print(" - 1 ly Nước cam (30,000đ) = 30,000đ (An uống riêng)")
            print(" - Người trả tiền trước cho quán: An")

            bill_data = {
                "title": "Bữa trưa đồng nghiệp 180k",
                "payer_name": "An",
                "participants": [{"display_name": "An"}, {"display_name": "Bình"}, {"display_name": "Cường"}],
                "items": [
                    {"name": "Cơm sườn", "unit_price_vnd": 50000, "quantity": 3, "assigned_participant_names": ["An", "Bình", "Cường"]},
                    {"name": "Nước cam", "unit_price_vnd": 30000, "quantity": 1, "assigned_participant_names": ["An"]},
                ],
                "tax_vnd": 0,
                "service_fee_vnd": 0,
                "discount_vnd": 0,
            }
            res = client.post("/v1/split-bills", json=bill_data, headers=agent_headers).json()["data"]

            print(f"\n📊 KẾT QUẢ TÍNH TOÁN CỦA BACKEND (Chính xác từng đồng):")
            for p in res["participant_shares"]:
                role = " (Người đã ứng tiền)" if p["is_payer"] else " (Cần thu tiền)"
                print(f" - {p['display_name']}: {p['total_share_vnd']:,} VND {role}")

            print("\n📲 CÁC MÃ THANH TOÁN / QR ĐƯỢC TỰ ĐỘNG SINH RA:")
            for cr in res["collection_requests"]:
                print(f"\n👉 Thu từ {cr['participant_name']} ({cr['requested_amount_vnd']:,}đ):")
                print(f"   Link thanh toán Sandbox: {cr['sandbox_payment_link']}")
                print(f"   Chuỗi mã QR sinh ra:     {cr['qr_payload'][:60]}...")

        elif choice == "4":
            print_banner("TÍNH NĂNG 4: SỐ DƯ HIỆN TẠI VÀ LỊCH SỬ GIAO DỊCH")
            sources = client.get("/v1/payment-sources", headers=user_headers).json()["data"]
            print("💰 CÁC NGUỒN TIỀN CỦA BẠN (AN):")
            for s in sources:
                credit_tag = f" (Hạn mức: {s['credit_limit_vnd']:,}đ)" if s["is_credit"] else ""
                print(f" - {s['display_name']} [{s['account_type']}]: {s['available_funds_vnd']:,} VND{credit_tag}")

            txs = client.get("/v1/transactions", headers=user_headers).json()["data"]
            print(f"\n📜 LỊCH SỬ GIAO DỊCH GẦN ĐÂY ({len(txs)} giao dịch):")
            for tx in txs[:5]:
                print(f" - [{tx['created_at'][:19]}] Số tiền: {tx['amount_vnd']:,}đ | Trạng thái: {tx['status']}")

        elif choice == "5":
            print("\n🔄 Đang khôi phục toàn bộ số dư và dữ liệu về trạng thái ban đầu...")
            client.post("/v1/demo/reset", headers=user_headers)
            print("✅ Đã khôi phục thành công! Số dư Ví MoMo trở lại 1,500,000 VND.")

        elif choice == "0":
            print("\nTạm biệt bạn!")
            break


if __name__ == "__main__":
    main()
