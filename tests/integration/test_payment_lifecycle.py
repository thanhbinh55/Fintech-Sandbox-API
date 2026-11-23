"""Integration tests for full Payment Intent API lifecycle."""
def test_full_payment_lifecycle_api(client, user_headers, agent_headers):
    # 1. Agent searches for unique contact "Lan"
    contact_res = client.get("/v1/contacts?q=Lan", headers=agent_headers)
    assert contact_res.status_code == 200
    lan_contact = contact_res.json()["data"]["matches"][0]
    recipient_account_id = lan_contact["recipient_account_id"]

    # 2. Agent creates payment draft for 120,000 VND
    draft_payload = {
        "recipient_account_id": recipient_account_id,
        "amount_vnd": 120000,
        "description": "Tien cafe cuoi tuan",
    }
    draft_res = client.post("/v1/payment-intents", json=draft_payload, headers=agent_headers)
    assert draft_res.status_code == 200
    intent_data = draft_res.json()["data"]
    intent_id = intent_data["id"]
    assert intent_data["status"] == "DRAFT"

    # 3. Agent requests ranked quotes
    quotes_res = client.post(f"/v1/payment-intents/{intent_id}/quotes", headers=agent_headers)
    assert quotes_res.status_code == 200
    quotes_data = quotes_res.json()["data"]["quotes"]
    assert len(quotes_data) >= 3

    # Select the recommended quote
    recommended_quote = next(q for q in quotes_data if q["recommended"] is True)

    # 4. Human user approves the recommended quote (User scope required)
    approval_res = client.post(
        f"/v1/payment-intents/{intent_id}/approve",
        json={"quote_id": recommended_quote["id"]},
        headers=user_headers,
    )
    assert approval_res.status_code == 200
    assert approval_res.json()["data"]["approved_quote_id"] == recommended_quote["id"]

    # 5. Human user executes payment (User scope required)
    exec_res = client.post(
        f"/v1/payment-intents/{intent_id}/execute",
        json={"idempotency_key": "idem-key-full-lifecycle-1"},
        headers=user_headers,
    )
    assert exec_res.status_code == 200
    exec_data = exec_res.json()["data"]
    assert exec_data["status"] == "SIMULATED_SUCCESS"
    assert exec_data["amount_transferred_vnd"] == 120000

    # 6. Check transaction history
    tx_res = client.get("/v1/transactions", headers=user_headers)
    assert tx_res.status_code == 200
    tx_list = tx_res.json()["data"]
    assert any(tx["payment_intent_id"] == intent_id for tx in tx_list)

