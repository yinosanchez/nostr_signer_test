import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
IDENTITIES_FILE = DATA_DIR / "identities.json"

RELAY_INTERNAL_URL = os.getenv("RELAY_INTERNAL_URL", "ws://127.0.0.1:7777")
RELAY_EXTERNAL_URL = os.getenv("RELAY_EXTERNAL_URL", "ws://localhost:7777")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")

