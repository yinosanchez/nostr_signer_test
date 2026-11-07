#!/usr/bin/env bash
set -e

echo "=== Ejecutando Suite de Tests Unitarios (Nostr Signer) ==="

if command -v docker &> /dev/null; then
    docker compose run --rm local-signer-app pytest -v tests/
else
    pytest -v app/tests/
fi

