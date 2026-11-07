from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

class IdentityMetadata(BaseModel):
    created_at_utc: str
    created_timestamp: int
    total_signatures_performed: int = 0
    last_used_utc: Optional[str] = None
    last_used_timestamp: Optional[int] = None
    description: Optional[str] = ""

class IdentityKeys(BaseModel):
    private_key_hex: str = Field(..., min_length=64, max_length=64)
    public_key_hex: str = Field(..., min_length=64, max_length=64)
    bech32_nsec: str = Field(..., pattern=r"^nsec1[0-9a-z]+$")
    bech32_npub: str = Field(..., pattern=r"^npub1[0-9a-z]+$")

class IdentityItem(BaseModel):
    id: str
    alias: str
    keys: IdentityKeys
    metadata: IdentityMetadata

class IdentitiesRegistry(BaseModel):
    version: str = "1.0"
    active_identity_id: Optional[str] = None
    identities: List[IdentityItem] = []

class GenerateIdentityRequest(BaseModel):
    alias: str = Field(..., min_length=1, max_length=60)
    description: Optional[str] = Field(default="", max_length=255)

class SwitchIdentityRequest(BaseModel):
    target_identity_id: str

class ConnectStringRequest(BaseModel):
    connection_string: str

class UpdateRelayRequest(BaseModel):
    relay_url: str = Field(..., min_length=5)

class BunkerStatusResponse(BaseModel):
    relay_connected: bool
    relay_internal_url: str
    relay_external_url: str
    current_relay_url: str
    available_preset_relays: List[str] = [
        "ws://localhost:7777",
        "wss://relay.damus.io",
        "wss://nos.lol",
        "wss://relay.nsec.app"
    ]
    active_identity: Optional[IdentityItem] = None
    bunker_connection_string: Optional[str] = None
    active_sessions_count: int = 0

