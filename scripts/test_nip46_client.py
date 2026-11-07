#!/usr/bin/env python3
"""
Test script simulating an external Nostr DApp / client connecting to the Local Bunker via NIP-46.
Usage:
    python scripts/test_nip46_client.py <bunker_uri_or_target_pubkey> [relay_url]
"""
from __future__ import annotations
import sys
import json
import asyncio
import urllib.parse
import websockets
from nostr_sdk import (
    Keys,
    PublicKey,
    EventBuilder,
    Kind,
    Tag,
    Timestamp,
    nip04_encrypt,
    nip04_decrypt,
    Event
)

async def test_bunker_client(bunker_target: str, relay_url: str = "ws://127.0.0.1:7777"):
    target_pubkey_hex = bunker_target
    if bunker_target.startswith("bunker://"):
        parsed = urllib.parse.urlparse(bunker_target)
        target_pubkey_hex = parsed.netloc
        qs = urllib.parse.parse_qs(parsed.query)
        if "relay" in qs:
            relay_url = qs["relay"][0]

    target_pubkey = PublicKey.parse(target_pubkey_hex)
    client_keys = Keys.generate()
    client_pubkey = client_keys.public_key()

    print(f"\n--- Iniciando Cliente de Prueba NIP-46 ---")
    print(f"Target Bunker Pubkey: {target_pubkey_hex}")
    print(f"Client Pubkey:        {client_pubkey.to_hex()}")
    print(f"Relay WebSocket:      {relay_url}")

    async with websockets.connect(relay_url) as ws:
        # Subscribe to responses from target bunker
        sub_id = f"test-sub-{client_pubkey.to_hex()[:8]}"
        filter_dict = {
            "kinds": [24133],
            "#p": [client_pubkey.to_hex()]
        }
        await ws.send(json.dumps(["REQ", sub_id, filter_dict]))
        print(f"Suscrito a respuestas kind 24133 en relay...")

        async def send_rpc_request(method: str, params: list, req_id: str):
            rpc_payload = {
                "id": req_id,
                "method": method,
                "params": params
            }
            plaintext = json.dumps(rpc_payload)
            encrypted = nip04_encrypt(client_keys.secret_key(), target_pubkey, plaintext)

            builder = EventBuilder(
                Kind(24133),
                encrypted
            ).tag(Tag.parse(["p", target_pubkey.to_hex()]))
            event = (
                builder.finalize(client_keys)
                if hasattr(builder, "finalize")
                else builder.to_event(client_keys)
            )
            await ws.send(json.dumps(["EVENT", json.loads(event.as_json())]))
            print(f">> Enviada petición RPC '{method}' (ID: {req_id})")

        async def wait_for_response(req_id: str, timeout: float = 10.0):
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                data = json.loads(raw_msg)
                if data[0] == "EVENT" and len(data) >= 3:
                    event_data = data[2]
                    sender = event_data.get("pubkey")
                    ciphertext = event_data.get("content", "")
                    try:
                        plaintext = nip04_decrypt(client_keys.secret_key(), PublicKey.parse(sender), ciphertext)
                        resp_rpc = json.loads(plaintext)
                        if resp_rpc.get("id") == req_id:
                            print(f"<< Recibida respuesta para '{req_id}': {resp_rpc}")
                            return resp_rpc
                    except Exception as e:
                        pass
            raise TimeoutError(f"Timeout esperando respuesta para {req_id}")

        # 1. Test connect
        print("\n1. Probando método 'connect'...")
        await send_rpc_request("connect", [client_pubkey.to_hex()], "req-conn-1")
        resp = await wait_for_response("req-conn-1")
        assert resp.get("result") == "ack", f"Fallo connect: {resp}"
        print("✓ Handshake 'connect' exitoso!")

        # 2. Test get_public_key
        print("\n2. Probando método 'get_public_key'...")
        await send_rpc_request("get_public_key", [], "req-pubkey-1")
        resp = await wait_for_response("req-pubkey-1")
        assert resp.get("result") == target_pubkey_hex, f"Mismatch pubkey: {resp}"
        print(f"✓ 'get_public_key' exitoso: {resp.get('result')}")

        # 3. Test sign_event
        print("\n3. Probando método 'sign_event' (Autoaprobación)...")
        now_ts = int(asyncio.get_event_loop().time())
        sample_event = {
            "kind": 1,
            "created_at": now_ts,
            "tags": [],
            "content": "Test post from NIP-46 simulated client"
        }
        await send_rpc_request("sign_event", [json.dumps(sample_event)], "req-sign-1")
        resp = await wait_for_response("req-sign-1")
        signed_event_str = resp.get("result")
        assert signed_event_str, f"Fallo firma: {resp}"
        
        signed_event = json.loads(signed_event_str)
        print("✓ 'sign_event' exitoso! Evento firmado recibido:")
        print(f"   Event ID:  {signed_event.get('id')}")
        print(f"   Signature: {signed_event.get('sig')}")
        print(f"   Pubkey:    {signed_event.get('pubkey')}")

        # Close subscription
        await ws.send(json.dumps(["CLOSE", sub_id]))
        print("\n--- Todas las pruebas NIP-46 concluyeron exitosamente ---\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/test_nip46_client.py <bunker_uri_o_pubkey_hex> [relay_url]")
        sys.exit(1)
    target = sys.argv[1]
    relay = sys.argv[2] if len(sys.argv) > 2 else "ws://127.0.0.1:7777"
    asyncio.run(test_bunker_client(target, relay))

