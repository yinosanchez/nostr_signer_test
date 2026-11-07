from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    # Use TestClient with base_url on localhost
    return TestClient(app, base_url="http://localhost:8000")

def test_security_headers_present(client):
    response = client.get("/api/identities")
    assert response.status_code == 200
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert "Content-Security-Policy" in response.headers

def test_api_generate_and_list_identities(client):
    # 1. Generate identity
    payload = {
        "alias": "API Test Identity",
        "description": "Created via TestClient"
    }
    create_resp = client.post("/api/identities/generate", json=payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["alias"] == "API Test Identity"
    assert created_data["keys"]["bech32_npub"].startswith("npub1")
    key_id = created_data["id"]

    # 2. List identities
    list_resp = client.get("/api/identities")
    assert list_resp.status_code == 200
    registry = list_resp.json()
    assert any(item["id"] == key_id for item in registry["identities"])

def test_api_bunker_status_and_relay_switch(client):
    # 1. Get status
    status_resp = client.get("/api/bunker/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "available_preset_relays" in data
    assert "current_relay_url" in data

    # 2. Switch relay to Damus
    relay_payload = {"relay_url": "wss://relay.damus.io"}
    switch_resp = client.post("/api/bunker/relay", json=relay_payload)
    assert switch_resp.status_code == 200
    switch_data = switch_resp.json()
    assert switch_data["current_relay_url"] == "wss://relay.damus.io"
    if switch_data["bunker_connection_string"]:
        assert "wss%3A%2F%2Frelay.damus.io" in switch_data["bunker_connection_string"]

    # 3. Switch back to local relay
    local_payload = {"relay_url": "ws://localhost:7777"}
    back_resp = client.post("/api/bunker/relay", json=local_payload)
    assert back_resp.status_code == 200

def test_api_trusted_host_rejection():
    # A request with an unauthorized Host header must be blocked by TrustedHostMiddleware
    bad_client = TestClient(app, base_url="http://malicious-domain.com")
    response = bad_client.get("/api/identities")
    assert response.status_code == 400

