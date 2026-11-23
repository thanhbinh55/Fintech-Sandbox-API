"""Security tests for scope enforcement and boundary protections."""
def test_agent_cannot_approve_payment(client, agent_headers, user_headers):
    # 1. Setup payment intent as agent
    contact_res = client.get("/v1/contacts?q=Lan", headers=agent_headers)
    recipient_acc_id = contact_res.json()["data"]["matches"][0]["recipient_account_id"]

    draft_res = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": recipient_acc_id, "amount_vnd": 50000, "description": "Security test"},
        headers=agent_headers,
    )
    intent_id = draft_res.json()["data"]["id"]

    quotes_res = client.post(f"/v1/payment-intents/{intent_id}/quotes", headers=agent_headers)
    quote_id = quotes_res.json()["data"]["quotes"][0]["id"]

    # 2. Agent attempts to call /approve -> MUST BE 403 FORBIDDEN
    approve_res = client.post(
        f"/v1/payment-intents/{intent_id}/approve",
        json={"quote_id": quote_id},
        headers=agent_headers,  # Scope is 'agent'
    )
    assert approve_res.status_code == 403
    assert approve_res.json()["error"]["code"] == "FORBIDDEN"


def test_agent_cannot_execute_payment(client, agent_headers, user_headers):
    # 1. Setup and approve as user
    contact_res = client.get("/v1/contacts?q=Lan", headers=agent_headers)
    recipient_acc_id = contact_res.json()["data"]["matches"][0]["recipient_account_id"]

    draft_res = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": recipient_acc_id, "amount_vnd": 50000, "description": "Security test 2"},
        headers=user_headers,
    )
    intent_id = draft_res.json()["data"]["id"]
    quotes_res = client.post(f"/v1/payment-intents/{intent_id}/quotes", headers=user_headers)
    quote_id = quotes_res.json()["data"]["quotes"][0]["id"]

    client.post(f"/v1/payment-intents/{intent_id}/approve", json={"quote_id": quote_id}, headers=user_headers)

    # 2. Agent attempts to call /execute -> MUST BE 403 FORBIDDEN
    exec_res = client.post(
        f"/v1/payment-intents/{intent_id}/execute",
        json={},
        headers=agent_headers,  # Scope is 'agent'
    )
    assert exec_res.status_code == 403
    assert exec_res.json()["error"]["code"] == "FORBIDDEN"


def test_agent_cannot_reset_demo(client, agent_headers):
    res = client.post("/v1/demo/reset", headers=agent_headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_negative_or_zero_amount_rejected(client, user_headers):
    res = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": "acc-1", "amount_vnd": -50000, "description": "Invalid"},
        headers=user_headers,
    )
    assert res.status_code == 422


def test_cross_session_isolation(client):
    # Create session 1
    s1 = client.post("/v1/demo/sessions", json={"scenario": "scenario_a"}).json()["data"]
    # Create session 2
    s2 = client.post("/v1/demo/sessions", json={"scenario": "scenario_a"}).json()["data"]

    s1_token = s1["credentials"]["user_token"]
    s2_token = s2["credentials"]["user_token"]

    # Get contact from session 2
    s2_contacts = client.get("/v1/contacts?q=Lan", headers={"Authorization": f"Bearer {s2_token}"}).json()["data"]["matches"]
    s2_contact_id = s2_contacts[0]["id"]
    s2_recipient_acc_id = s2_contacts[0]["recipient_account_id"]

    # User in session 1 tries to access contact from session 2 -> 404
    contact_cross = client.get(f"/v1/contacts/{s2_contact_id}", headers={"Authorization": f"Bearer {s1_token}"})
    assert contact_cross.status_code == 404

    # User in session 1 tries to create payment intent with session 2 recipient account -> 404
    intent_cross = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": s2_recipient_acc_id, "amount_vnd": 50000, "description": "Cross session"},
        headers={"Authorization": f"Bearer {s1_token}"},
    )
    assert intent_cross.status_code == 404
