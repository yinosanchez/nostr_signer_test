from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from src.config import IDENTITIES_FILE, DATA_DIR
from src.models.identity import IdentitiesRegistry, IdentityItem

class JSONIdentitiesStore:
    def __init__(self, file_path: Path = IDENTITIES_FILE):
        self.file_path = file_path
        self._lock = asyncio.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensures the parent directory and identities file exist with valid initial structure."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            initial_data = IdentitiesRegistry().model_dump()
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)

    async def load_registry(self) -> IdentitiesRegistry:
        """Loads and parses the identities registry from disk."""
        async with self._lock:
            self._ensure_file_exists()
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            return IdentitiesRegistry.model_validate(raw_data)

    async def save_registry(self, registry: IdentitiesRegistry) -> None:
        """Atomically saves the identities registry to disk with human-readable 2-space indentation."""
        async with self._lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.file_path.with_suffix(".tmp")
            data_dict = registry.model_dump()
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data_dict, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.file_path)

    async def get_active_identity(self) -> Optional[IdentityItem]:
        """Returns the currently active identity item, if any."""
        registry = await self.load_registry()
        if not registry.active_identity_id:
            return None
        for item in registry.identities:
            if item.id == registry.active_identity_id:
                return item
        return None

    async def add_identity(self, item: IdentityItem, make_active: bool = False) -> IdentityItem:
        """Appends a new identity and optionally marks it as active."""
        registry = await self.load_registry()
        registry.identities.append(item)
        if make_active or not registry.active_identity_id:
            registry.active_identity_id = item.id
        await self.save_registry(registry)
        return item

    async def set_active_identity(self, identity_id: str) -> Optional[IdentityItem]:
        """Switches the active identity to the target identity_id."""
        registry = await self.load_registry()
        target = None
        for item in registry.identities:
            if item.id == identity_id:
                target = item
                break
        if not target:
            return None
        registry.active_identity_id = identity_id
        await self.save_registry(registry)
        return target

    async def record_signature_performed(self, identity_id: str) -> None:
        """Increments signature counter and updates last used timestamp."""
        registry = await self.load_registry()
        for item in registry.identities:
            if item.id == identity_id:
                now = datetime.now(timezone.utc)
                item.metadata.total_signatures_performed += 1
                item.metadata.last_used_utc = now.isoformat()
                item.metadata.last_used_timestamp = int(now.timestamp())
                break
        await self.save_registry(registry)

identities_store = JSONIdentitiesStore()

