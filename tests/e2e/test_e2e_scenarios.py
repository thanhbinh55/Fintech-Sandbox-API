"""End-to-End Tests E2E-01 through E2E-07."""
import pytest


def test_e2e_01_chat_to_pay_unique_recipient(client, agent_headers, user_headers):
    """E2E-01: Chat-to-Pay with unique recipient (e.g. Lan)."""
    # 1. Contact lookup
    contacts = client.get("/v1/contacts?q=Lan", headers=agent_headers).json()["data"]
    assert contacts["is_ambiguous"] is False
    recipient_id = contacts["matches"][0]["recipient_account_id"]

    # 2. Draft intent
    intent = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": recipient_id, "amount_vnd": 150000, "description": "Tien an toi"},
        headers=agent_headers,
    ).json()["data"]

    # 3. Get quotes
    quotes = client.post(f"/v1/payment-intents/{intent['id']}/quotes", headers=agent_headers).json()["data"]["quotes"]
    assert len(quotes) > 0
    rec_quote = next(q for q in quotes if q["recommended"] is True)

    # 4. User approval
    appr = client.post(
        f"/v1/payment-intents/{intent['id']}/approve",
        json={"quote_id": rec_quote["id"]},
        headers=user_headers,
    ).json()["data"]
    assert appr["payment_intent_id"] == intent["id"]

    # 5. User execution
    exec_res = client.post(
        f"/v1/payment-intents/{intent['id']}/execute",
        json={"idempotency_key": "e2e-01-unique"},
        headers=user_headers,
    ).json()["data"]
    assert exec_res["status"] == "SIMULATED_SUCCESS"


def test_e2e_02_chat_to_pay_ambiguous_recipient(client, agent_headers):
    """E2E-02: Chat-to-Pay with ambiguous recipient (e.g. Minh)."""
    contacts = client.get("/v1/contacts?q=Minh", headers=agent_headers).json()["data"]
    assert contacts["is_ambiguous"] is True
    assert len(contacts["matches"]) >= 2
    # Verify AI has information needed to clarify
    names = [m["display_name"] for m in contacts["matches"]]
    assert "Nguyễn Minh" in names and "Trần Minh" in names


def test_e2e_03_smart_routing_multiple_sources(client, agent_headers):
    """E2E-03: Smart Routing evaluating multiple sources, fees, and cashback."""
    sources = client.get("/v1/payment-sources", headers=agent_headers).json()["data"]
    contact = client.get("/v1/contacts?q=Lan", headers=agent_headers).json()["data"]["matches"][0]

    intent = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": contact["recipient_account_id"], "amount_vnd": 200000, "description": "Routing test"},
        headers=agent_headers,
    ).json()["data"]

    quotes = client.post(f"/v1/payment-intents/{intent['id']}/quotes", headers=agent_headers).json()["data"]["quotes"]
    assert len(quotes) == len(sources)

    # Verify ranking: recommended quote has lowest effective cost among eligible
    recommended = next(q for q in quotes if q["recommended"] is True)
    for q in quotes:
        if q["eligible"]:
            assert recommended["effective_cost_vnd"] <= q["effective_cost_vnd"]


def test_e2e_04_bill_splitting_and_collection(client, agent_headers, user_headers):
    """E2E-04: Bill splitting and collection full lifecycle."""
    bill_payload = {
        "title": "Pizza Party",
        "payer_name": "An",
        "participants": [{"display_name": "An"}, {"display_name": "Bình"}],
        "items": [{"name": "Pizza", "unit_price_vnd": 200000, "quantity": 1}],
        "tax_vnd": 20000,
        "service_fee_vnd": 0,
        "discount_vnd": 0,
    }
    bill = client.post("/v1/split-bills", json=bill_payload, headers=agent_headers).json()["data"]
    col_req = bill["collection_requests"][0]
    assert col_req["requested_amount_vnd"] == 110000

    # Settle
    client.post(f"/v1/split-bills/{bill['id']}/requests/{col_req['request_id']}/settle", json={}, headers=user_headers)
    status = client.get(f"/v1/split-bills/{bill['id']}/status", headers=agent_headers).json()["data"]
    assert status["is_fully_settled"] is True


def test_e2e_05_insufficient_funds_rejection(client, agent_headers, user_headers):
    """E2E-05: Insufficient funds handling."""
    contact = client.get("/v1/contacts?q=Lan", headers=agent_headers).json()["data"]["matches"][0]
    # Request 50,000,000 VND (exceeds all accounts)
    intent = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": contact["recipient_account_id"], "amount_vnd": 50000000, "description": "Big money"},
        headers=agent_headers,
    ).json()["data"]

    quotes_res = client.post(f"/v1/payment-intents/{intent['id']}/quotes", headers=agent_headers).json()["data"]["quotes"]
    # All quotes must be ineligible
    for q in quotes_res:
        assert q["eligible"] is False

    # Attempting to approve ineligible quote fails
    res = client.post(
        f"/v1/payment-intents/{intent['id']}/approve",
        json={"quote_id": quotes_res[0]["id"]},
        headers=user_headers,
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INSUFFICIENT_FUNDS"


def test_e2e_06_duplicate_execution_request(client, agent_headers, user_headers):
    """E2E-06: Duplicate execution returns cached transaction safely."""
    contact = client.get("/v1/contacts?q=Lan", headers=agent_headers).json()["data"]["matches"][0]
    intent = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": contact["recipient_account_id"], "amount_vnd": 30000, "description": "Duplicate test"},
        headers=agent_headers,
    ).json()["data"]

    quotes = client.post(f"/v1/payment-intents/{intent['id']}/quotes", headers=agent_headers).json()["data"]["quotes"]
    client.post(f"/v1/payment-intents/{intent['id']}/approve", json={"quote_id": quotes[0]["id"]}, headers=user_headers)

    res1 = client.post(
        f"/v1/payment-intents/{intent['id']}/execute",
        json={"idempotency_key": "e2e-dup-06"},
        headers=user_headers,
    )
    res2 = client.post(
        f"/v1/payment-intents/{intent['id']}/execute",
        json={"idempotency_key": "e2e-dup-06"},
        headers=user_headers,
    )

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["data"]["transaction_id"] == res2.json()["data"]["transaction_id"]


def test_e2e_07_demo_session_isolation_and_reset(client, user_headers, demo_session):
    """E2E-07: Demo session isolation and reproducible reset."""
    # Reset caller's session
    reset_res = client.post("/v1/demo/reset", headers=user_headers)
    assert reset_res.status_code == 200
    data = reset_res.json()["data"]
    assert data["id"] == demo_session.id

    # Accounts should be restored to initial balances
    sources = client.get("/v1/payment-sources", headers={"Authorization": f"Bearer {data['credentials']['user_token']}"}).json()["data"]
    wallet = next(s for s in sources if s["account_type"] == "EWALLET")
    assert wallet["available_funds_vnd"] == 1500000

