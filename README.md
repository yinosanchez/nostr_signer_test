# Nostr Local Signer (NIP-46 Bunker)

Aplicación web local y conteinerizada para la gestión de identidades criptográficas Nostr (`secp256k1` / BIP-340) y firmador remoto con soporte de **NIP-46 (Nostr Connect / Bunker)**, autoaprobación de firmas y relay Nostr local (`nostr-rs-relay`).

---

## Características

- **Gestión de Identidades Nostr:** Generación de pares criptográficos con CSPRNG y derivación X-only (BIP-340), codificación Bech32 (`nsec1...` / `npub1...`).
- **Persistencia en Plano:** Almacenamiento legible y estructurado en `./data/identities.json` con metadatos (contador de firmas, fechas y timestamps).
- **NIP-46 Bunker Remoto:** Métodos RPC soportados: `connect`, `get_public_key` y `sign_event`.
- **Política de Autoaprobación:** Firma automática de eventos para sesiones activas válidas.
- **Conmutación Estricta:** Al cambiar de identidad activa, las suscripciones y sesiones de la llave previa son invalidadas y cerradas inmediatamente.
- **Relay Local en Docker:** Contenedor de `nostr-rs-relay` en el puerto `7777`.
- **Seguridad:** Aislamiento en `127.0.0.1` / `localhost` con `TrustedHostMiddleware`, `CORSMiddleware` y cabeceras de protección HTTP (CSP, X-Frame-Options, X-Content-Type-Options).
- **Interfaz Web Local:** SPA minimalista con jQuery, servida en `http://127.0.0.1:8000`.

---

## Arquitectura de Servicios

| Servicio | Contenedor | Puerto Local | Descripción |
| :--- | :--- | :--- | :--- |
| **`local-signer-app`** | `nostr-local-signer` | `127.0.0.1:8000` | FastAPI + Uvicorn + `nostr-sdk` + Frontend Web |
| **`local-relay`** | `nostr-local-relay` | `127.0.0.1:7777` | Servidor Nostr local (`nostr-rs-relay`) |

---

## Cómo Ejecutar con Docker Compose

1. **Levantar los contenedores:**
   ```bash
   docker compose up --build -d
   ```

   o simplemente:
   ```bash
   ./run.sh
   ```

2. **Abrir la interfaz web:**
   Navega en tu navegador a:
   ```text
   http://127.0.0.1:8000
   ```

3. **Detener los servicios:**
   ```bash
   docker compose down
   ```

---

## Endpoints de la API REST Interna

- `GET /api/identities`: Lista las identidades almacenadas y el ID de la activa.
- `POST /api/identities/generate`: Genera una nueva identidad (`{ "alias": "Nombre", "description": "..." }`).
- `POST /api/identities/switch`: Conmuta la identidad activa e invalida la previa (`{ "target_identity_id": "<id>" }`).
- `GET /api/bunker/status`: Retorna el estado del Bunker, relay y connection string activo.
- `POST /api/bunker/connect-string`: Inicia handshake desde una cadena `nostrconnect://...`.

---

## Conexión con Stacker News (y DApps Web HTTPS)

Stacker News (`https://stacker.news`) opera bajo HTTPS y requiere comunicación WebSocket cifrada (`wss://`).

1. En la interfaz web (`http://127.0.0.1:8000`), dirígete a la sección **Relay de Comunicación NIP-46**.
2. Selecciona **Damus (`wss://relay.damus.io`)** o **Nos.lol (`wss://nos.lol`)** y haz clic en **Cambiar Relay**.
3. El connection string se actualizará automáticamente a:
   ```text
   bunker://<tu_pubkey>?relay=wss%3A%2F%2Frelay.damus.io
   ```
4. Haz clic en **Copiar URI**.
5. En Stacker News:
   - Ve a **Login** -> **Nostr (NIP-46 / Bunker)**.
   - Pega tu connection string.
6. Tu Bunker local recibirá la solicitud cifrada vía el relay de Damus, la autoaprobará y firmará el evento de inicio de sesión sin necesidad de abrir puertos en tu router ni exponer tu máquina.

---

## Ejecución de Tests Unitarios

La suite de pruebas cubre criptografía (`secp256k1`, BIP-340, Bech32), persistencia atómica en plano, RPC NIP-46 y endpoints REST con middlewares de seguridad:

```bash
# Ejecutar tests dentro del contenedor Docker
./test.sh

# O mediante docker compose directamente:
docker compose run --rm local-signer-app pytest -v tests/
```

---

## Verificación de Persistencia

El archivo de identidades se almacena en el host dentro de:
```text
./data/identities.json
```
Este archivo está excluido del control de versiones (`.gitignore`) y persiste entre reinicios o recreaciones de los contenedores Docker.
