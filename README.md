<div align="center">

# Enc-Chat: E2EE Secure Messaging System
[![Playwright E2E](https://img.shields.io/badge/playwright-tested-brightgreen.svg)](e2e/tests)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100.0-009688.svg?logo=fastapi)](backend)
[![Vue3](https://img.shields.io/badge/Vue.js-3.0-4FC08D.svg?logo=vue.js)](frontend)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg?logo=docker)](docker-compose.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

A high-performance, real-time messaging application featuring complete End-to-End Encryption (E2EE) powered by the Signal Protocol's principles (Double Ratchet Algorithm).

<br>

🌐 Language / 语言 <br>
**English** | [简体中文](README.zh-CN.md)

</div>

---

## 🔒 Security Architecture Highlights
Enc-Chat ensures that the server can **never** decipher the plaintext contents of messages, pictures, or files. The server acts purely as an opaque delivery envelope router.

- **E2EE Private & Group Chat**: AES-256-GCM message encryption paired with RSA key exchange. Group chats utilize sender-keys with perfect forward secrecy mapping to broadcast sockets.
- **Double Ratchet Mechanism**: Implemented in frontend browser crypto context (`window.crypto.subtle`) ensuring session limits and forward/backward confidentiality.
- **Ephemeral Keys & PFS**: New keys are rolled per logical message phase using HKDF (HMAC-based Key Derivation).
- **In-Memory E2EE Envelope Storage**: Once downloaded to the client, cipher blobs reside purely in local runtime constraints. The backend immediately strips outbox payloads.
- **True Multi-Device Concurrent Auth**: Single user sessions can span PC and mobile concurrently, decrypting individual stream branches via synchronized pre-keys.
- **DevOps Safe**: Includes fully automated Canaries, Zero-Knowledge Rollbacks, and Playwright regressions spanning message recall to aggressive device-kicking payloads (`F9-09` verified).

## 🚀 Quick Start (Docker Run)

Launch the fully containerized application via `docker-compose`. This boots a unified NGINX Frontend, FastAPI Backend, and MySQL engine.

```bash
# 1. Copy sample environment files
cp docker/.env.example docker/.env

# 2. Build and launch the environment stack
docker-compose --env-file docker/.env up -d --build

# 3. Access securely local UI
https://localhost:23456
```

## 📂 Project Structure (Monorepo)

```text
├── backend/                  # FastAPI & SQLAlchemy Database Engines
│   ├── app/e2ee/             # Python E2EE Routes & Broadcast Handlers
│   ├── app/chat/             # WebSocket Multi-Multiplexer System
│   └── tests/                # Pytest Fixtures
├── frontend/                 # Vue 3 Vite PWA
│   ├── src/views/            # E2EE ChatRoom Contexts
│   ├── src/utils/e2ee/       # Browser WebCrypto Implementations
│   └── src/components/       # UI Overridables
├── e2e/                      # Playwright E2E Integration Testing
│   ├── tests/F9-02-chat      # Private & Group Encryption Sync Spec
│   ├── tests/F9-08-load      # 50+ Concurrent Member Sync Stress Tests
│   └── tests/F9-09-recall    # Async Message Revocation Specifications
└── docker/                   # Rollback, Canary, and Release Configuration
```

## 🧪 E2E End-to-End Testing

We provide a bulletproof Chromium testing pipeline with custom isolated environments hitting the local database nodes directly.

```bash
# Navigate to the E2E directory (example absolute path)
cd d:\jetbrains_proj\pycharm_proj\enc_chat_proj\e2e
# Install dependencies if not already done
npm ci

# Run entire F9 lifecycle (Chat, Media, Groups, Kicks, Loads)
npx playwright test --project=chromium --reporter=list
```

### Canary Rollback Drilling
To test database restoration in an isolated canary instance, run the rollback script from the root directory:
```bash
# Note: If you are running from Windows PowerShell, prefix with 'bash'
bash docker/rollback_drill.sh
```

## 📄 License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**. 
See the [LICENSE](LICENSE) file for more details.
> Every unit and UI automation inherently operates against E2E browser limits, dynamically bootstrapping RSA Key-Pairs across multi-page fixtures.

## 🧰 Tech Stack
- **Database**: MySQL 8.4
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy, Uvicorn (WebSockets)
- **Frontend**: Vue 3 (Composition API), Vite, Element Plus, Axios (Requires Node.js `^20.19.0 || >=22.12.0`)
- **E2E Ops**: Playwright Chromium, Docker Compose (isolated DB Drops)

## 📸 Screenshots & Demonstrations

<div align="center">

![Enc-Chat UI Overview](screenshots/merged.png)

*Login, Registration, Private E2EE Chat, Group Chat, Friend Requests & Notifications*

</div>

## 🛠️ Testing Environment & Restoring Prod Defaults (F9 Milestone)

During the F9 milestone (E2EE Double Ratchet, Group concurrency, Multi-device, Disaster Recovery), non-destructive configuration overrides were made to satisfy extreme load testing.

### 1. Backend Rate-Limit Bumping (`backend/.env`)
* **Modified**: `WS_MAX_MESSAGES_PER_MINUTE=500`.
* **Reason**: F9-08 testing includes massive "concurrent off-line message syncs", spiking request throughput and triggering 429 Too Many Requests normally.
* **To Restoring Prod**: Set `WS_MAX_MESSAGES_PER_MINUTE=60` to mitigate malicious flooding.

### 2. Canary and Rollback Integrations (`docker-compose.canary.yml`)
* **Modified**: A dedicated canary stack mapping to port `23457` was added to test AES/Hex limits seamlessly without polluting developers' `enc_chat_db`.
* **To Restore Prod**: Simply run `docker compose -f docker/docker-compose.canary.yml down -v` to wipe the temporary canary testing mounts if you're experiencing disk load. 

### 3. CI/CD E2E Pass Context
If cloning to a fresh CI pipeline, ensure `WS_MAX_MESSAGES_PER_MINUTE=500` is exported, keep `--ssl-keyfile` on the backend, and run `npx playwright test --project=chromium` securely.
