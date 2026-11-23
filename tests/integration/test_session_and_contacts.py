"""Integration tests for Sessions and Contact search/ambiguity."""
def test_create_session_and_retrieve_me(client):
    res = client.post("/v1/demo/sessions", json={"scenario": "scenario_a", "display_name": "Integration Session"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert "credentials" in data
    assert data["seed_scenario"] == "scenario_a"

    user_token = data["credentials"]["user_token"]
    me_res = client.get("/v1/demo/sessions/me", headers={"Authorization": f"Bearer {user_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["data"]["id"] == data["id"]


def test_contact_search_ambiguity(client, agent_headers):
    # Query "Minh" matches both "Nguyễn Minh" and "Trần Minh"
    res = client.get("/v1/contacts?q=Minh", headers=agent_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_ambiguous"] is True
    assert len(data["matches"]) == 2
    assert "Vui lòng chỉ định rõ" in data["clarification_message"]


def test_contact_search_unique_match(client, agent_headers):
    # Query "Lan" uniquely matches "Lan"
    res = client.get("/v1/contacts?q=Lan", headers=agent_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_ambiguous"] is False
    assert len(data["matches"]) == 1
    assert data["matches"][0]["display_name"] == "Lan"


def test_reset_demo_session(client, user_headers, demo_session):
    # Spend some money or modify state, then reset
    res = client.post("/v1/demo/reset", headers=user_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["id"] == demo_session.id

