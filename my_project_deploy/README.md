# Enc Chat Deployment Bundle

Language / 语言: **English** | [简体中文](README.zh-CN.md)

This directory contains the online deployment bundle for the GHCR-based release stack.

For air-gapped deployment using `enc-chat-release.tar`, see `README.offline.md`.

## Files

- `docker-compose.yml`: deployment stack definition
- `.env.example`: deployment environment template
- `start.sh`: Linux/macOS startup script
- `start.bat`: Windows startup script

## Requirements

- Docker Engine or Docker Desktop
- Docker Compose v2

## Quick Start

```bash
cp .env.example .env
```

If you need to use your own GHCR images, edit `.env` and set:

```env
BACKEND_IMAGE=ghcr.io/<github-namespace>/enc-chat-backend:<tag>
FRONTEND_IMAGE=ghcr.io/<github-namespace>/enc-chat-frontend:<tag>
```

If the images are private, log in first:

```bash
echo "$CR_PAT" | docker login ghcr.io -u <github-username> --password-stdin
```

Start the stack:

```bash
docker compose pull
docker compose up -d
```

Or use the helper scripts:

```bash
# Online mode (default)
./start.sh

# Offline mode using enc-chat-release.tar
./start.sh offline
```

Windows:

```bat
REM Online mode (default)
start.bat

REM Offline mode using enc-chat-release.tar
start.bat offline
```

Default URL:

```text
https://localhost:23456
```

## Stop

```bash
docker compose down
```

## Logs

```bash
docker compose logs -f
```

## Notes

- Current startup scripts pull images from GHCR; they do not load `enc-chat-release.tar`.
- Run `./start.sh offline` or `start.bat offline` to load `enc-chat-release.tar` and start without pulling from GHCR.
- Public GHCR images can be pulled anonymously; private images require `docker login ghcr.io`.
- Application and database data are stored in Docker volumes.
