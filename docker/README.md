# Docker Packaging

## Chosen scheme

This project is packaged with a multi-image stack:

- `frontend`: builds the Vue app and serves it with Nginx over local TLS.
- `backend`: runs FastAPI/Uvicorn.
- `mysql`: runs an isolated MySQL instance.

## Why not a single image

Single-image packaging is simpler for a short-lived demo, but it is weaker here because it mixes web server, FastAPI, and MySQL into one container, makes persistence and upgrades harder, enlarges the blast radius of any failure, and usually needs an extra process supervisor.

For this project, the split stack is better because frontend/backend/database lifecycles are already independent, Docker volumes can isolate sensitive runtime files, and the final deployment is closer to a real production topology.

## Security handling

Sensitive local files are excluded from image build contexts:

- `backend/.env`
- `backend/uploaded_files_v2/`
- `backend/avatars/`
- `backend/group_avatars/`
- `backend/app.log`
- `backend/server_private.pem`

At runtime, the backend writes new sensitive state into the Docker volume mounted at `/data` instead of baking host files into the image:

- e2ee attachment blobs: `/data/uploaded_files_v2`
- avatars: `/data/avatars`
- group avatars: `/data/group_avatars`
- backend log: `/data/app.log`
- generated secrets: `/data/secrets/`

This keeps the Docker stack independent from the current local project state.

Keep `backend_data` and `mysql_data` together. The backend stores the generated JWT secret, DB encryption key, and runtime file data in `backend_data`, and the MySQL data in `mysql_data` depends on those secrets remaining stable.

## Test-to-release cutover

If the current project data is disposable test data, do not migrate it.

- Build fresh images from the current source tree only; runtime data is kept out of the image build by the Dockerfiles and `.dockerignore` files.
- Start the release stack with fresh `mysql_data` and `backend_data` volumes.
- Do not copy local `backend/.env`, `backend/uploaded_files_v2/`, `backend/avatars/`, `backend/group_avatars/`, logs, or private keys into the deployment host.
- Let the backend generate fresh runtime secrets and storage state inside `/data` on first boot, or inject production secrets explicitly through environment variables.

For a host that has already run the old test stack, remove the old Docker volumes before the first release boot:

```sh
docker compose --env-file docker/.env down -v
docker volume prune -f
```

Run `docker volume prune -f` only if that host is dedicated to this project or you have confirmed no other containers still need old anonymous volumes.

## Local TLS

The frontend container generates a self-signed TLS certificate on first start and stores it in the `frontend_tls` Docker volume. The app is exposed on `https://localhost:23456` by default.

## Start

```sh
cp docker/.env.example docker/.env
docker compose --env-file docker/.env up -d --build
```

## Stop

```sh
docker compose --env-file docker/.env down
```

## Reset Docker-only data

```sh
docker compose --env-file docker/.env down -v
```

That removes only the Docker stack data volumes and does not touch the current local backend/frontend runtime files.
