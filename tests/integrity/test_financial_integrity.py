"""Financial integrity tests: idempotency, balance conservation, and double-entry consistency."""
from app.models import Account, LedgerEntry, Transaction


def test_idempotency_prevents_duplicate_charge(client, user_headers):
    # Setup intent and approval
    contact_res = client.get("/v1/contacts?q=Lan", headers=user_headers)
    recipient_acc_id = contact_res.json()["data"]["matches"][0]["recipient_account_id"]

    draft = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": recipient_acc_id, "amount_vnd": 50000, "description": "Idempotent payment"},
        headers=user_headers,
    ).json()["data"]

    quotes = client.post(f"/v1/payment-intents/{draft['id']}/quotes", headers=user_headers).json()["data"]["quotes"]
    quote_id = quotes[0]["id"]

    client.post(f"/v1/payment-intents/{draft['id']}/approve", json={"quote_id": quote_id}, headers=user_headers)

    # Initial balances
    sources_before = client.get("/v1/payment-sources", headers=user_headers).json()["data"]
    wallet_before = next(s["available_funds_vnd"] for s in sources_before if s["source_id"] == quotes[0]["source_account_id"])

    # First Execution with Idempotency Key
    idem_key = "test-idempotency-key-xyz-123"
    exec1 = client.post(
        f"/v1/payment-intents/{draft['id']}/execute",
        json={"idempotency_key": idem_key},
        headers=user_headers,
    )
    assert exec1.status_code == 200
    tx1_id = exec1.json()["data"]["transaction_id"]

    # Second Execution with SAME Idempotency Key
    exec2 = client.post(
        f"/v1/payment-intents/{draft['id']}/execute",
        json={"idempotency_key": idem_key},
        headers=user_headers,
    )
    assert exec2.status_code == 200
    tx2_id = exec2.json()["data"]["transaction_id"]
    assert tx1_id == tx2_id, "Idempotent retry must return the exact same transaction ID"

    # Verify balance was debited EXACTLY ONCE
    sources_after = client.get("/v1/payment-sources", headers=user_headers).json()["data"]
    wallet_after = next(s["available_funds_vnd"] for s in sources_after if s["source_id"] == quotes[0]["source_account_id"])

    amount_debited = quotes[0]["amount_debited_vnd"]
    assert wallet_after == wallet_before - amount_debited


def test_double_entry_ledger_consistency(client, user_headers, db_session, demo_session):
    # Execute a transfer and verify ledger entries
    contact_res = client.get("/v1/contacts?q=Lan", headers=user_headers)
    recipient_acc_id = contact_res.json()["data"]["matches"][0]["recipient_account_id"]

    draft = client.post(
        "/v1/payment-intents",
        json={"recipient_account_id": recipient_acc_id, "amount_vnd": 70000, "description": "Ledger check"},
        headers=user_headers,
    ).json()["data"]

    quotes = client.post(f"/v1/payment-intents/{draft['id']}/quotes", headers=user_headers).json()["data"]["quotes"]
    quote = quotes[0]

    client.post(f"/v1/payment-intents/{draft['id']}/approve", json={"quote_id": quote["id"]}, headers=user_headers)
    exec_res = client.post(f"/v1/payment-intents/{draft['id']}/execute", json={}, headers=user_headers)
    assert exec_res.status_code == 200

    tx_id = exec_res.json()["data"]["transaction_id"]

    # In DB, verify ledger entries for this transaction
    ledger_entries = db_session.query(LedgerEntry).filter_by(transaction_id=tx_id).all()
    total_debit = sum(e.amount_vnd for e in ledger_entries if e.direction == "DEBIT")
    total_credit = sum(e.amount_vnd for e in ledger_entries if e.direction == "CREDIT")

    # Invariant: Total Debits == Total Credits across the entire system
    assert total_debit == total_credit

    # Specific debit to source account matches quote amount_debited_vnd
    source_debit = sum(
        e.amount_vnd
        for e in ledger_entries
        if e.account_id == quote["source_account_id"] and e.direction == "DEBIT"
    )
    assert source_debit == quote["amount_debited_vnd"]
