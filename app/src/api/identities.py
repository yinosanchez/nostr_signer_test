from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from src.models.identity import (
    IdentitiesRegistry,
    IdentityItem,
    GenerateIdentityRequest,
    SwitchIdentityRequest
)
from src.storage.json_store import identities_store
from src.crypto.nostr_crypto import NostrCryptoService
from src.bunker.engine import bunker_engine

router = APIRouter(prefix="/api/identities", tags=["Identities"])

@router.get("", response_model=IdentitiesRegistry)
async def list_identities():
    """Lists all stored identities, their metadata, and indicates which one is active."""
    return await identities_store.load_registry()

@router.post("/generate", response_model=IdentityItem, status_code=status.HTTP_201_CREATED)
async def generate_identity(payload: GenerateIdentityRequest):
    """
    Generates a new secp256k1 keypair, computes X-only pubkey & bech32 nsec/npub,
    and saves it to the plaintext identities.json file.
    """
    new_identity = NostrCryptoService.generate_new_identity(
        alias=payload.alias,
        description=payload.description or ""
    )
    # If no active identity currently exists, make this new one active
    current_active = await identities_store.get_active_identity()
    make_active = current_active is None

    saved_identity = await identities_store.add_identity(new_identity, make_active=make_active)
    
    if make_active:
        await bunker_engine.switch_identity(saved_identity.id)

    return saved_identity

@router.post("/switch")
async def switch_identity(payload: SwitchIdentityRequest):
    """
    Switches active identity:
    1. Immediately invalidates and purges sessions/subscriptions for the previous key.
    2. Activates the target key and updates subscriptions on the local relay.
    """
    switched = await bunker_engine.switch_identity(payload.target_identity_id)
    if not switched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Identity '{payload.target_identity_id}' not found."
        )

    return {
        "status": "switched",
        "active_identity_id": switched.id,
        "invalidated_previous": True,
        "alias": switched.alias,
        "npub": switched.keys.bech32_npub
    }

