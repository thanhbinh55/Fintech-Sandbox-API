"""Integration tests for Bill Splitting endpoints, QR generation, and settlement."""
def test_bill_splitting_full_api_flow(client, user_headers, agent_headers):
    # 1. Create a split bill for 3 participants
    bill_payload = {
        "title": "Bữa tối nhóm",
        "payer_name": "An",
        "participants": [
            {"display_name": "An"},
            {"display_name": "Bình"},
            {"display_name": "Cường"},
        ],
        "items": [
            {"name": "Lẩu thái", "unit_price_vnd": 240000, "quantity": 1, "assigned_participant_names": []},
            {"name": "Trà đá", "unit_price_vnd": 10000, "quantity": 3, "assigned_participant_names": []},
        ],
        "tax_vnd": 0,
        "service_fee_vnd": 0,
        "discount_vnd": 0,
    }
    # Total: 270,000 VND / 3 = 90,000 VND each

    create_res = client.post("/v1/split-bills", json=bill_payload, headers=agent_headers)
    assert create_res.status_code == 200
    bill_data = create_res.json()["data"]
    split_id = bill_data["id"]

    assert bill_data["total_bill_amount_vnd"] == 270000
    assert len(bill_data["collection_requests"]) == 2  # Bình and Cường

    col_req_binh = next(cr for cr in bill_data["collection_requests"] if cr["participant_name"] == "Bình")
    assert col_req_binh["requested_amount_vnd"] == 90000

    # 2. Get QR code for Bình's share
    qr_res = client.get(
        f"/v1/split-bills/{split_id}/requests/{col_req_binh['request_id']}/qr",
        headers=agent_headers,
    )
    assert qr_res.status_code == 200
    qr_data = qr_res.json()["data"]
    assert "SANDBOX_VND_PAYMENT" in qr_data["qr_payload"]
    assert "sandbox.wallet.local" in qr_data["sandbox_payment_link"]

    # 3. Simulate Bình paying his share
    settle_res = client.post(
        f"/v1/split-bills/{split_id}/requests/{col_req_binh['request_id']}/settle",
        json={"collected_amount_vnd": 90000},
        headers=user_headers,
    )
    assert settle_res.status_code == 200
    assert settle_res.json()["data"]["status"] == "PAID"

    # 4. Check split status
    status_res = client.get(f"/v1/split-bills/{split_id}/status", headers=agent_headers)
    assert status_res.status_code == 200
    status_data = status_res.json()["data"]
    assert status_data["total_collected_vnd"] == 180000  # An's 90k + Bình's 90k
    assert status_data["remaining_to_collect_vnd"] == 90000  # Cường remaining
    assert status_data["is_fully_settled"] is False
