from __future__ import annotations
import asyncio
import json
import logging
import urllib.parse
from typing import Optional, Dict, Any
import websockets
from nostr_sdk import (
    Keys,
    SecretKey,
    PublicKey,
    EventBuilder,
    Kind,
    Tag,
    Timestamp,
    Event
)
from src.config import RELAY_INTERNAL_URL, RELAY_EXTERNAL_URL
from src.storage.json_store import identities_store
from src.bunker.handlers import rpc_handler
from src.models.identity import IdentityItem

logger = logging.getLogger("bunker_engine")

class BunkerEngine:
    PRESET_RELAYS = [
        "ws://localhost:7777",
        "wss://relay.damus.io",
        "wss://nos.lol",
        "wss://relay.nsec.app"
    ]

    def __init__(self):
        self.relay_internal_url = RELAY_INTERNAL_URL
        self.relay_external_url = RELAY_EXTERNAL_URL
        self.active_relay_url = self.relay_external_url
        self.is_running = False
        self.relay_connected = False
        self._current_task: Optional[asyncio.Task] = None
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._sub_id: Optional[str] = None
        self._active_identity: Optional[IdentityItem] = None
        self._active_keys: Optional[Keys] = None

    def _is_ws_open(self) -> bool:
        """Robustly checks if the websocket connection is open across websockets versions."""
        if not self._ws:
            return False
        state = getattr(self._ws, "state", None)
        if state is not None:
            return getattr(state, "name", str(state)) == "OPEN"
        if hasattr(self._ws, "open"):
            return bool(self._ws.open)
        if hasattr(self._ws, "closed"):
            return not bool(self._ws.closed)
        return self.relay_connected

    def get_bunker_connection_string(self) -> Optional[str]:
        if not self._active_identity:
            return None
        pubkey = self._active_identity.keys.public_key_hex
        encoded_relay = urllib.parse.quote(self.active_relay_url, safe="")
        return f"bunker://{pubkey}?relay={encoded_relay}"

    async def get_status(self) -> Dict[str, Any]:
        active = await identities_store.get_active_identity()
        self._active_identity = active
        session_count = rpc_handler.get_session_count(active.id if active else None)

        return {
            "relay_connected": self.relay_connected,
            "relay_internal_url": self.relay_internal_url,
            "relay_external_url": self.relay_external_url,
            "current_relay_url": self.active_relay_url,
            "available_preset_relays": self.PRESET_RELAYS,
            "active_identity": active.model_dump() if active else None,
            "bunker_connection_string": self.get_bunker_connection_string(),
            "active_sessions_count": session_count,
        }

    async def set_target_relay(self, new_relay: str) -> Dict[str, Any]:
        """
        Updates the relay used by the Bunker.
        If local relay is chosen, uses internal Docker address for connection.
        Otherwise connects directly to the specified public WSS relay.
        """
        clean_relay = new_relay.strip()
        is_local = clean_relay in [
            "ws://localhost:7777",
            "ws://127.0.0.1:7777",
            "ws://local-relay:7777",
            self.relay_external_url
        ]

        if is_local:
            self.relay_internal_url = RELAY_INTERNAL_URL
            self.active_relay_url = self.relay_external_url
        else:
            self.relay_internal_url = clean_relay
            self.active_relay_url = clean_relay

        logger.info(f"Target relay changed to '{self.active_relay_url}' (internal: '{self.relay_internal_url}')")

        # Restart loop to connect to new relay
        if self.is_running:
            if self._current_task:
                self._current_task.cancel()
                try:
                    await self._current_task
                except asyncio.CancelledError:
                    pass
            await self._close_ws()
            self._current_task = asyncio.create_task(self._relay_connection_loop())

        return await self.get_status()

    async def start(self):
        """Starts the background bunker service."""
        if self.is_running:
            return
        self.is_running = True
        self._active_identity = await identities_store.get_active_identity()
        if self._active_identity:
            self._setup_keys(self._active_identity)
        self._current_task = asyncio.create_task(self._relay_connection_loop())
        logger.info("Bunker engine started.")

    async def stop(self):
        """Stops the bunker background service."""
        self.is_running = False
        if self._current_task:
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
            self._current_task = None
        await self._close_ws()
        logger.info("Bunker engine stopped.")

    def _setup_keys(self, identity: IdentityItem):
        secret_hex = identity.keys.private_key_hex
        self._active_keys = Keys.parse(secret_hex)

    async def switch_identity(self, target_identity_id: str) -> Optional[IdentityItem]:
        """
        Atomically switches identity:
        1. Closes previous subscription & purges sessions.
        2. Sets new active identity.
        3. Restarts relay subscription with new public key.
        """
        logger.info(f"Switching active identity to '{target_identity_id}'")
        
        # Invalidate previous sessions
        if self._active_identity:
            rpc_handler.clear_sessions(self._active_identity.id)

        # Close existing subscription on relay
        if self._ws and self._sub_id:
            try:
                close_msg = json.dumps(["CLOSE", self._sub_id])
                await self._ws.send(close_msg)
            except Exception as e:
                logger.warning(f"Could not send CLOSE message: {e}")

        # Update in store
        target_identity = await identities_store.set_active_identity(target_identity_id)
        if not target_identity:
            return None

        self._active_identity = target_identity
        self._setup_keys(target_identity)

        # Re-subscribe on active WS if connected
        if self._is_ws_open():
            await self._send_subscription(self._ws)

        return target_identity

    async def _close_ws(self):
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self.relay_connected = False

    async def _send_subscription(self, ws: websockets.WebSocketClientProtocol):
        if not self._active_identity:
            logger.info("No active identity configured; subscription skipped.")
            return

        active_pubkey = self._active_identity.keys.public_key_hex
        self._sub_id = f"bunker-sub-{active_pubkey[:8]}"

        filter_dict = {
            "kinds": [24133],
            "#p": [active_pubkey]
        }
        req_msg = json.dumps(["REQ", self._sub_id, filter_dict])
        await ws.send(req_msg)
        logger.info(f"Subscribed to kind 24133 for active pubkey {active_pubkey} with sub_id '{self._sub_id}'")

    async def _relay_connection_loop(self):
        """Continuously maintains connection to the local Nostr relay."""
        while self.is_running:
            try:
                logger.info(f"Connecting to local Nostr relay at {self.relay_internal_url}...")
                async with websockets.connect(self.relay_internal_url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    self.relay_connected = True
                    logger.info("Connected to local Nostr relay successfully.")

                    # Send subscription for active identity
                    await self._send_subscription(ws)

                    # Message loop
                    async for message in ws:
                        if not self.is_running:
                            break
                        await self._process_relay_message(message, ws)

            except asyncio.CancelledError:
                break
            except Exception as err:
                self.relay_connected = False
                logger.warning(f"Relay connection error ({err}). Reconnecting in 3 seconds...")
                await asyncio.sleep(3)
            finally:
                self.relay_connected = False

    async def _process_relay_message(self, raw_msg: str, ws: websockets.WebSocketClientProtocol):
        try:
            data = json.loads(raw_msg)
            if not isinstance(data, list) or len(data) < 2:
                return

            msg_type = data[0]

            if msg_type == "EVENT" and len(data) >= 3:
                # ["EVENT", <subscription_id>, <event_json>]
                event_dict = data[2]
                await self._handle_incoming_nip46_event(event_dict, ws)

        except Exception as err:
            logger.error(f"Error processing relay message: {err}", exc_info=True)

    async def _handle_incoming_nip46_event(self, event_dict: Dict[str, Any], ws: websockets.WebSocketClientProtocol):
        if not self._active_identity or not self._active_keys:
            return

        kind = event_dict.get("kind")
        if kind != 24133:
            return

        sender_pubkey_hex = event_dict.get("pubkey")
        ciphertext = event_dict.get("content", "")
        req_event_id = event_dict.get("id")

        if not sender_pubkey_hex or not ciphertext:
            return

        sender_pubkey = PublicKey.parse(sender_pubkey_hex)
        secret_key = self._active_keys.secret_key()

        # Decrypt payload
        try:
            plaintext, cipher_type = rpc_handler.decrypt_payload(secret_key, sender_pubkey, ciphertext)
            rpc_req = json.loads(plaintext)
        except Exception as err:
            logger.warning(f"Could not decrypt/parse NIP-46 event from {sender_pubkey_hex}: {err}")
            return

        # Execute RPC handler with auto-approval
        rpc_resp = await rpc_handler.handle_rpc_request(
            request_rpc=rpc_req,
            client_pubkey_hex=sender_pubkey_hex,
            identity_id=self._active_identity.id,
            active_keys=self._active_keys
        )

        # Encrypt response and publish to relay
        try:
            resp_json_str = json.dumps(rpc_resp)
            encrypted_resp = rpc_handler.encrypt_payload(secret_key, sender_pubkey, resp_json_str, cipher_type)

            tags_to_add = [
                Tag.parse(["p", sender_pubkey.to_hex()])
            ]
            if req_event_id:
                tags_to_add.append(Tag.parse(["e", str(req_event_id)]))

            resp_builder = EventBuilder(
                Kind(24133),
                encrypted_resp
            ).tags(tags_to_add)

            resp_event = (
                resp_builder.finalize(self._active_keys)
                if hasattr(resp_builder, "finalize")
                else resp_builder.to_event(self._active_keys)
            )
            publish_msg = json.dumps(["EVENT", json.loads(resp_event.as_json())])
            await ws.send(publish_msg)
            logger.info(f"Published NIP-46 response for method '{rpc_req.get('method')}' to client '{sender_pubkey_hex}'")

        except Exception as err:
            logger.error(f"Failed to publish NIP-46 response: {err}", exc_info=True)

    async def handle_connect_string(self, connection_string: str) -> Dict[str, Any]:
        """
        Parses a nostrconnect:// string and initiates a connect handshake event.
        nostrconnect://<client_pubkey>?relay=<relay>&secret=<secret>
        """
        if not self._active_identity or not self._active_keys:
            raise ValueError("No active identity to connect with.")

        parsed = urllib.parse.urlparse(connection_string)
        if parsed.scheme != "nostrconnect":
            raise ValueError("Invalid scheme: must be nostrconnect://")

        client_pubkey_hex = parsed.netloc
        qs = urllib.parse.parse_qs(parsed.query)
        secret = qs.get("secret", [None])[0]

        # Register session locally
        if self._active_identity.id not in rpc_handler.active_sessions:
            rpc_handler.active_sessions[self._active_identity.id] = set()
        rpc_handler.active_sessions[self._active_identity.id].add(client_pubkey_hex)

        # Send ACK / connect acknowledgment to client if WS is open
        if self._is_ws_open():
            client_pubkey = PublicKey.parse(client_pubkey_hex)
            connect_resp_rpc = {
                "id": f"conn-{client_pubkey_hex[:8]}",
                "result": "ack",
                "error": None
            }
            resp_str = json.dumps(connect_resp_rpc)
            encrypted = rpc_handler.encrypt_payload(
                self._active_keys.secret_key(),
                client_pubkey,
                resp_str,
                "nip04"
            )
            builder = EventBuilder(
                Kind(24133),
                encrypted
            ).tag(Tag.parse(["p", client_pubkey.to_hex()]))
            event = (
                builder.finalize(self._active_keys)
                if hasattr(builder, "finalize")
                else builder.to_event(self._active_keys)
            )
            await self._ws.send(json.dumps(["EVENT", json.loads(event.as_json())]))

        return {
            "status": "connected",
            "client_pubkey": client_pubkey_hex,
            "secret": secret
        }

bunker_engine = BunkerEngine()

