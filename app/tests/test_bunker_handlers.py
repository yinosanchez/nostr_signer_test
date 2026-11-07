from __future__ import annotations
import json
import pytest
from nostr_sdk import Keys, Event
from src.bunker.handlers import NIP46RPCHandler

@pytest.fixture
def rpc_handler():
    return NIP46RPCHandler()

@pytest.mark.asyncio
async def test_rpc_connect(rpc_handler, sample_keys):
    client_pubkey = "3bf0c63fcb93463407af9babd5e937d4e33483067416258b988ef3edabf8935b"
    identity_id = "test-identity-1"

    req = {
        "id": "req-1",
        "method": "connect",
        "params": [client_pubkey]
    }

    resp = await rpc_handler.handle_rpc_request(req, client_pubkey, identity_id, sample_keys)
    assert resp["id"] == "req-1"
    assert resp["result"] == "ack"
    assert resp["error"] is None
    assert rpc_handler.get_session_count(identity_id) == 1

@pytest.mark.asyncio
async def test_rpc_get_public_key(rpc_handler, sample_keys):
    client_pubkey = "3bf0c63fcb93463407af9babd5e937d4e33483067416258b988ef3edabf8935b"
    identity_id = "test-identity-1"

    req = {
        "id": "req-2",
        "method": "get_public_key",
        "params": []
    }

    resp = await rpc_handler.handle_rpc_request(req, client_pubkey, identity_id, sample_keys)
    assert resp["id"] == "req-2"
    assert resp["result"] == sample_keys.public_key().to_hex()
    assert resp["error"] is None

@pytest.mark.asyncio
async def test_rpc_sign_event_auto_approved(rpc_handler, sample_keys):
    client_pubkey = "3bf0c63fcb93463407af9babd5e937d4e33483067416258b988ef3edabf8935b"
    identity_id = "test-identity-1"

    unsigned_event = {
        "kind": 1,
        "content": "Automated signing test via NIP-46",
        "created_at": 1700000000,
        "tags": [["t", "test"]]
    }

    req = {
        "id": "req-3",
        "method": "sign_event",
        "params": [json.dumps(unsigned_event)]
    }

    resp = await rpc_handler.handle_rpc_request(req, client_pubkey, identity_id, sample_keys)
    assert resp["id"] == "req-3"
    assert resp["error"] is None
    assert resp["result"] is not None

    # Parse and verify the signed event
    signed_event_dict = json.loads(resp["result"])
    assert signed_event_dict["pubkey"] == sample_keys.public_key().to_hex()
    assert signed_event_dict["content"] == "Automated signing test via NIP-46"
    assert len(signed_event_dict["sig"]) == 128  # 64 bytes hex

    event_obj = Event.from_json(resp["result"])
    assert event_obj.verify()

@pytest.mark.asyncio
async def test_rpc_sign_event_invalid_params(rpc_handler, sample_keys):
    client_pubkey = "3bf0c63fcb93463407af9babd5e937d4e33483067416258b988ef3edabf8935b"
    identity_id = "test-identity-1"

    req = {
        "id": "req-4",
        "method": "sign_event",
        "params": []  # Missing event payload
    }

    resp = await rpc_handler.handle_rpc_request(req, client_pubkey, identity_id, sample_keys)
    assert resp["result"] is None
    assert "Invalid params" in resp["error"]

@pytest.mark.asyncio
async def test_rpc_unsupported_method(rpc_handler, sample_keys):
    client_pubkey = "3bf0c63fcb93463407af9babd5e937d4e33483067416258b988ef3edabf8935b"
    identity_id = "test-identity-1"

    req = {
        "id": "req-5",
        "method": "unknown_nip46_call",
        "params": []
    }

    resp = await rpc_handler.handle_rpc_request(req, client_pubkey, identity_id, sample_keys)
    assert resp["result"] is None
    assert "Unsupported NIP-46 method" in resp["error"]

def test_clear_sessions(rpc_handler):
    rpc_handler.active_sessions["id-1"] = {"client-a", "client-b"}
    rpc_handler.active_sessions["id-2"] = {"client-c"}

    # Clear specific identity
    rpc_handler.clear_sessions("id-1")
    assert rpc_handler.get_session_count("id-1") == 0
    assert rpc_handler.get_session_count("id-2") == 1

    # Clear all
    rpc_handler.clear_sessions()
    assert rpc_handler.get_session_count("id-2") == 0

