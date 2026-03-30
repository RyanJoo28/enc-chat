# Enc Chat Offline Deployment

Language / 语言: **English** | [简体中文](README.offline.zh-CN.md)

This guide is for air-gapped or restricted-network environments that cannot pull images from GHCR.

## Included offline image tags

The release archive `enc-chat-release.tar` contains these local image tags:

- `enc-chat-docker-backend:latest`
- `enc-chat-docker-frontend:latest`

## Requirements

- Docker Engine or Docker Desktop
- Docker Compose v2
- `enc-chat-release.tar`

## Quick Start

Create a deployment env file:

```bash
cp .env.example .env
```

Point Docker Compose at the locally loaded image tags:

```env
BACKEND_IMAGE=enc-chat-docker-backend:latest
FRONTEND_IMAGE=enc-chat-docker-frontend:latest
```

Load the offline image bundle:

```bash
docker load -i enc-chat-release.tar
```

Start the stack without pulling from GHCR:

```bash
docker compose up -d
```

Or use the helper scripts in offline mode:

```bash
./start.sh offline
```

Windows:

```bat
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

- Do not run `docker compose pull` in offline mode.
- `./start.sh offline` and `start.bat offline` automatically load `enc-chat-release.tar` and force the bundled local image tags.
- If `.env` does not set `BACKEND_IMAGE` and `FRONTEND_IMAGE`, Docker Compose falls back to the GHCR image references in `docker-compose.yml`.
- Application and database data are stored in Docker volumes.
