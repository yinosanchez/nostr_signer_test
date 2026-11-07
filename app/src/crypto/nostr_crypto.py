from __future__ import annotations
import uuid
from datetime import datetime, timezone
from nostr_sdk import Keys
from src.models.identity import IdentityItem, IdentityKeys, IdentityMetadata

class NostrCryptoService:
    @staticmethod
    def generate_new_identity(alias: str, description: str = "") -> IdentityItem:
        """
        Generates a new secp256k1 keypair using CSPRNG via nostr-sdk,
        derives X-only public key and bech32 nsec/npub strings,
        and initializes metadata.
        """
        keys = Keys.generate()
        secret_key = keys.secret_key()
        public_key = keys.public_key()

        now = datetime.now(timezone.utc)
        now_ts = int(now.timestamp())
        now_iso = now.isoformat()

        identity_id = f"id-{uuid.uuid4()}"

        identity_keys = IdentityKeys(
            private_key_hex=secret_key.to_hex(),
            public_key_hex=public_key.to_hex(),
            bech32_nsec=secret_key.to_bech32(),
            bech32_npub=public_key.to_bech32(),
        )

        metadata = IdentityMetadata(
            created_at_utc=now_iso,
            created_timestamp=now_ts,
            total_signatures_performed=0,
            last_used_utc=None,
            last_used_timestamp=None,
            description=description or "",
        )

        return IdentityItem(
            id=identity_id,
            alias=alias.strip(),
            keys=identity_keys,
            metadata=metadata,
        )

