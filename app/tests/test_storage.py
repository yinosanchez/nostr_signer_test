from __future__ import annotations
import json
import pytest
from src.crypto.nostr_crypto import NostrCryptoService

@pytest.mark.asyncio
async def test_init_empty_registry(mock_store):
    registry = await mock_store.load_registry()
    assert registry.version == "1.0"
    assert registry.active_identity_id is None
    assert len(registry.identities) == 0
    assert mock_store.file_path.exists()

@pytest.mark.asyncio
async def test_add_and_auto_activate_identity(mock_store):
    id1 = NostrCryptoService.generate_new_identity("First Key")
    await mock_store.add_identity(id1)

    active = await mock_store.get_active_identity()
    assert active is not None
    assert active.id == id1.id
    assert active.alias == "First Key"

    # Adding a second key should not override active unless explicitly requested
    id2 = NostrCryptoService.generate_new_identity("Second Key")
    await mock_store.add_identity(id2, make_active=False)

    active_after = await mock_store.get_active_identity()
    assert active_after.id == id1.id

@pytest.mark.asyncio
async def test_switch_identity(mock_store):
    id1 = NostrCryptoService.generate_new_identity("Key A")
    id2 = NostrCryptoService.generate_new_identity("Key B")
    await mock_store.add_identity(id1)
    await mock_store.add_identity(id2)

    # Switch to Key B
    switched = await mock_store.set_active_identity(id2.id)
    assert switched is not None
    assert switched.id == id2.id

    active = await mock_store.get_active_identity()
    assert active.id == id2.id

    # Switch to non-existent ID
    invalid = await mock_store.set_active_identity("non-existent-id")
    assert invalid is None

@pytest.mark.asyncio
async def test_record_signature_performed(mock_store):
    id1 = NostrCryptoService.generate_new_identity("Signature Counter Key")
    await mock_store.add_identity(id1)

    assert id1.metadata.total_signatures_performed == 0
    assert id1.metadata.last_used_timestamp is None

    await mock_store.record_signature_performed(id1.id)

    active = await mock_store.get_active_identity()
    assert active.metadata.total_signatures_performed == 1
    assert active.metadata.last_used_timestamp is not None
    assert active.metadata.last_used_utc is not None

@pytest.mark.asyncio
async def test_file_indentation_format(mock_store):
    id1 = NostrCryptoService.generate_new_identity("Format Check Key")
    await mock_store.add_identity(id1)

    with open(mock_store.file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify that file has 2-space indentation and is valid JSON
    assert '  "version": "1.0"' in content
    assert '  "identities": [' in content
    parsed = json.loads(content)
    assert parsed["active_identity_id"] == id1.id

