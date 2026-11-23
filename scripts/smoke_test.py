"""Quick smoke test script verifying FastAPI app startup and basic endpoints."""
import sys
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    print("1. Testing GET /health...")
    res = client.get("/health")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["success"] is True
    print("   Health OK:", data["data"])

    print("2. Testing GET /ready...")
    res = client.get("/ready")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["success"] is True
    print("   Readiness OK:", data["data"])

    print("3. Testing POST /v1/demo/sessions (Scenario A)...")
    res = client.post("/v1/demo/sessions", json={"scenario": "scenario_a", "display_name": "Smoke Test Session"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    session_data = res.json()["data"]
    session_id = session_data["id"]
    user_token = session_data["credentials"]["user_token"]
    agent_token = session_data["credentials"]["agent_token"]
    print(f"   Session created: {session_id}")

    print("4. Testing GET /v1/payment-sources with agent token...")
    res = client.get("/v1/payment-sources", headers={"Authorization": f"Bearer {agent_token}"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    sources = res.json()["data"]
    print(f"   Found {len(sources)} payment sources:")
    for s in sources:
        print(f"     - {s['display_name']} ({s['account_type']}): {s['available_funds_vnd']:,} VND")

    print("5. Testing GET /v1/contacts?q=Minh with agent token (Ambiguity Test)...")
    res = client.get("/v1/contacts?q=Minh", headers={"Authorization": f"Bearer {agent_token}"})
    assert res.status_code == 200
    contacts_data = res.json()["data"]
    assert contacts_data["is_ambiguous"] is True
    assert len(contacts_data["matches"]) == 2
    print(f"   Ambiguity correctly detected! Matches: {[c['display_name'] for c in contacts_data['matches']]}")

    print("\n--- ALL SMOKE TESTS PASSED SUCCESSFULLY! ---")
