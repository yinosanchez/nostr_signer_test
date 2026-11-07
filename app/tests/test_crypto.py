from __future__ import annotations
import pytest
from nostr_sdk import Keys, EventBuilder, Kind
from src.crypto.nostr_crypto import NostrCryptoService

def test_generate_new_identity_structure():
    alias = "Test Identity"
    desc = "A key generated for unit testing"
    identity = NostrCryptoService.generate_new_identity(alias, desc)

    # Basic fields
    assert identity.id.startswith("id-")
    assert identity.alias == alias
    assert identity.metadata.description == desc
    assert identity.metadata.total_signatures_performed == 0
    assert identity.metadata.created_timestamp > 0
    assert identity.metadata.last_used_timestamp is None

    # Key validations
    keys = identity.keys
    assert len(keys.private_key_hex) == 64
    assert len(keys.public_key_hex) == 64
    assert keys.bech32_nsec.startswith("nsec1")
    assert keys.bech32_npub.startswith("npub1")

def test_key_derivation_consistency():
    identity = NostrCryptoService.generate_new_identity("Consistency Test")
    parsed_keys = Keys.parse(identity.keys.private_key_hex)

    # Derived public key must match exactly
    assert parsed_keys.public_key().to_hex() == identity.keys.public_key_hex
    assert parsed_keys.secret_key().to_bech32() == identity.keys.bech32_nsec
    assert parsed_keys.public_key().to_bech32() == identity.keys.bech32_npub

def test_bip340_schnorr_signature():
    identity = NostrCryptoService.generate_new_identity("Signer Test")
    keys = Keys.parse(identity.keys.private_key_hex)

    builder = EventBuilder(Kind(1), "Hello BIP-340 Schnorr")
    event = builder.finalize(keys) if hasattr(builder, "finalize") else builder.to_event(keys)

    # Verify signature validity
    assert event.verify()
    assert event.author().to_hex() == identity.keys.public_key_hex
    assert len(event.id().to_hex()) == 64

