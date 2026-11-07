from __future__ import annotations
import os
import shutil
import tempfile
from pathlib import Path
import pytest
from nostr_sdk import Keys
from src.storage.json_store import JSONIdentitiesStore

@pytest.fixture
def temp_data_dir():
    """Creates a temporary data directory for tests and cleans up after."""
    temp_dir = tempfile.mkdtemp(prefix="nostr_test_data_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def mock_store(temp_data_dir):
    """Provides a fresh JSONIdentitiesStore instance backed by temporary storage."""
    file_path = temp_data_dir / "identities.json"
    store = JSONIdentitiesStore(file_path=file_path)
    return store

@pytest.fixture
def sample_keys():
    """Generates a pair of Nostr Keys for testing."""
    return Keys.generate()

