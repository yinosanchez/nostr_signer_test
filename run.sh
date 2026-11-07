#!/usr/bin/env bash
set -e

echo "=== Nostr Local Signer (NIP-46 Bunker) ==="
echo "Iniciando contenedores con Docker Compose..."

docker compose up --build

