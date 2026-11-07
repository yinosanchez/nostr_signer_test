from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from src.api.identities import router as identities_router
from src.api.bunker import router as bunker_router
from src.bunker.engine import bunker_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nostr_signer_app")

STATIC_DIR = Path(__file__).parent / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start NIP-46 Bunker engine
    logger.info("Initializing Nostr Bunker Engine...")
    await bunker_engine.start()
    yield
    # Shutdown: Stop engine
    logger.info("Shutting down Nostr Bunker Engine...")
    await bunker_engine.stop()

app = FastAPI(
    title="Nostr Local Remote Signer (NIP-46)",
    description="Local web app for Nostr identity management and NIP-46 remote signing.",
    version="1.0.0",
    lifespan=lifespan
)

# 1. TrustedHostMiddleware - restricts traffic to 127.0.0.1 and localhost
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "127.0.0.1",
        "localhost",
        "127.0.0.1:8000",
        "localhost:8000",
        "testserver"
    ]
)

# 2. CORSMiddleware - strict local origin restriction
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 3. Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://code.jquery.com; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self';"
    )
    return response

# API Routers
app.include_router(identities_router)
app.include_router(bunker_router)

# Mount Static Files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon():
    return Response(status_code=204)

