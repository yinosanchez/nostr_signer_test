from __future__ import annotations
import json
import logging
from typing import Dict, Any, Optional, Set, Tuple
from nostr_sdk import (
    Keys,
    SecretKey,
    PublicKey,
    EventBuilder,
    Kind,
    Tag,
    Timestamp,
    nip04_decrypt,
    nip04_encrypt,
    nip44_decrypt,
    nip44_encrypt
)
from src.storage.json_store import identities_store

logger = logging.getLogger("bunker_handlers")

class NIP46RPCHandler:
    def __init__(self):
        # Maps active_identity_id -> set of connected client pubkey hexes
        self.active_sessions: Dict[str, Set[str]] = {}

    def clear_sessions(self, identity_id: Optional[str] = None):
        """Invalidates active sessions for an identity (or all if None)."""
        if identity_id:
            if identity_id in self.active_sessions:
                del self.active_sessions[identity_id]
        else:
            self.active_sessions.clear()

    def get_session_count(self, identity_id: Optional[str]) -> int:
        if not identity_id or identity_id not in self.active_sessions:
            return 0
        return len(self.active_sessions[identity_id])

    def decrypt_payload(self, secret_key: SecretKey, sender_pubkey: PublicKey, ciphertext: str) -> tuple[str, str]:
        """
        Attempts to decrypt ciphertext using NIP-04 first, falling back to NIP-44.
        Returns (plaintext, cipher_type).
        """
        try:
            plaintext = nip04_decrypt(secret_key, sender_pubkey, ciphertext)
            return plaintext, "nip04"
        except Exception:
            try:
                plaintext = nip44_decrypt(secret_key, sender_pubkey, ciphertext)
                return plaintext, "nip44"
            except Exception as e:
                raise ValueError(f"Failed to decrypt with NIP-04 and NIP-44: {e}")

    def encrypt_payload(self, secret_key: SecretKey, recipient_pubkey: PublicKey, plaintext: str, cipher_type: str = "nip04") -> str:
        """Encrypts payload using the specified cipher type."""
        if cipher_type == "nip44":
            return nip44_encrypt(secret_key, recipient_pubkey, plaintext)
        return nip04_encrypt(secret_key, recipient_pubkey, plaintext)

    async def handle_rpc_request(
        self,
        request_rpc: Dict[str, Any],
        client_pubkey_hex: str,
        identity_id: str,
        active_keys: Keys
    ) -> Dict[str, Any]:
        """
        Executes RPC method: 'connect', 'get_public_key', or 'sign_event'.
        Applies auto-approval policy.
        """
        req_id = request_rpc.get("id", "")
        method = request_rpc.get("method", "")
        params = request_rpc.get("params") or []

        logger.info(f"NIP-46 RPC request: method='{method}', id='{req_id}', client='{client_pubkey_hex}'")

        if identity_id not in self.active_sessions:
            self.active_sessions[identity_id] = set()

        if method == "connect":
            # params: [client_pubkey, optional_secret]
            self.active_sessions[identity_id].add(client_pubkey_hex)
            logger.info(f"Client '{client_pubkey_hex}' connected to identity '{identity_id}'")
            return {
                "id": req_id,
                "result": "ack",
                "error": None
            }

        elif method == "get_public_key":
            pubkey_hex = active_keys.public_key().to_hex()
            return {
                "id": req_id,
                "result": pubkey_hex,
                "error": None
            }

        elif method == "sign_event":
            if not params or not isinstance(params[0], str):
                return {
                    "id": req_id,
                    "result": None,
                    "error": "Invalid params: expected serialized event string as first parameter"
                }

            try:
                unsigned_dict = json.loads(params[0])
            except Exception as err:
                return {
                    "id": req_id,
                    "result": None,
                    "error": f"Invalid JSON event: {err}"
                }

            # Build and sign Nostr event using active_keys
            try:
                kind_num = int(unsigned_dict.get("kind", 1))
                content = unsigned_dict.get("content", "")
                created_at_sec = int(unsigned_dict.get("created_at", Timestamp.now().as_secs()))
                
                # Parse tags
                raw_tags = unsigned_dict.get("tags", [])
                tags_list = []
                for tag_row in raw_tags:
                    if isinstance(tag_row, list) and len(tag_row) > 0:
                        tag_name = tag_row[0]
                        tag_args = tag_row[1:] if len(tag_row) > 1 else []
                        tags_list.append(Tag.parse([tag_name] + tag_args))

                builder = EventBuilder(Kind(kind_num), content)
                if tags_list:
                    builder = builder.tags(tags_list)
                builder = builder.custom_created_at(Timestamp.from_secs(created_at_sec))

                signed_event = (
                    builder.finalize(active_keys)
                    if hasattr(builder, "finalize")
                    else builder.to_event(active_keys)
                )
                signed_json_str = signed_event.as_json()

                # Record signature in metadata and update storage
                await identities_store.record_signature_performed(identity_id)
                logger.info(f"Auto-approved and signed event kind {kind_num} (ID: {signed_event.id().to_hex()})")

                return {
                    "id": req_id,
                    "result": signed_json_str,
                    "error": None
                }
            except Exception as err:
                logger.error(f"Error signing event: {err}", exc_info=True)
                return {
                    "id": req_id,
                    "result": None,
                    "error": f"Failed to sign event: {err}"
                }

        else:
            return {
                "id": req_id,
                "result": None,
                "error": f"Unsupported NIP-46 method '{method}'"
            }

rpc_handler = NIP46RPCHandler()

