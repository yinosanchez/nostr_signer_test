from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from src.models.identity import (
    BunkerStatusResponse,
    ConnectStringRequest,
    UpdateRelayRequest
)
from src.bunker.engine import bunker_engine

router = APIRouter(prefix="/api/bunker", tags=["Bunker"])

@router.get("/status", response_model=BunkerStatusResponse)
async def get_bunker_status():
    """Returns the live status of the Bunker engine, relay connection, and active connection string."""
    status_data = await bunker_engine.get_status()
    return BunkerStatusResponse(**status_data)

@router.post("/relay", response_model=BunkerStatusResponse)
async def update_target_relay(payload: UpdateRelayRequest):
    """
    Switches the active relay used by the Bunker (e.g. wss://relay.damus.io for Stacker News).
    Automatically updates the bunker connection string and reconnects the listener.
    """
    try:
        updated_status = await bunker_engine.set_target_relay(payload.relay_url)
        return BunkerStatusResponse(**updated_status)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to switch relay: {err}"
        )

@router.post("/connect-string")
async def connect_by_string(payload: ConnectStringRequest):
    """Initiates connection and handshakes with a client from a nostrconnect:// string."""
    try:
        result = await bunker_engine.handle_connect_string(payload.connection_string)
        return result
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection failed: {err}"
        )

