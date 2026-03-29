# AGENTS.md
Use this file as the operating guide for coding agents in this repository.
Favor existing project patterns over generic framework defaults.
Current git layout: `/` is not a git repo; `backend/` and `frontend/` are separate git repos.
## Rule Files
- Scanned for `.cursorrules`, `.cursor/rules/`, and `.github/copilot-instructions.md`.
- None were present when this file was updated.
- If any of those files appear later, they override this document where they conflict.
## Repo Layout
- `backend/`: FastAPI + SQLAlchemy chat backend with MySQL in normal runtime and SQLite in tests.
- `frontend/`: Vue 3 + Vite + Element Plus frontend.
- `backend/tests/`: pytest suite for chat manager, E2EE services, file validation, and acceptance flows.
- `docker-compose.yml` and `docker/README.md`: local stack plus Docker packaging/runtime notes.
- `certs/` and `my_project_deploy/`: local TLS assets and image-based deployment bundle.
## Important Paths
- `backend/app/main.py`: app creation, middleware, startup maintenance, and router registration.
- `backend/app/database/__init__.py`, `backend/app/database/models.py`, `backend/app/database/crud.py`: engine/session setup, schema layer, and reusable persistence helpers.
- `backend/app/user/routes.py`, `backend/app/user/friend_routes.py`, `backend/app/user/dependencies.py`: auth, profile, friend flows, and auth resolution.
- `backend/app/chat/routes.py`, `backend/app/chat/access_routes.py`, `backend/app/chat/manager.py`: chat, group access, and websocket broadcast logic.
- `backend/app/e2ee/`: end-to-end encryption routes, websocket handling, and service layer.
- `backend/app/utils/encryption.py`: reuse existing RSA/AES and metadata encryption helpers instead of reimplementing crypto.
- `backend/app/utils/log_utils.py`: structured logging helpers via `build_log_payload()` and `log_event()`.
- `backend/app/settings.py`: env parsing plus runtime paths for uploads, avatars, logs, and secrets.
- `frontend/src/views/Login.vue`, `frontend/src/views/ChatRoom.vue`: primary UI screens and backend error/detail translation maps.
- `frontend/src/utils/runtime.js`, `frontend/src/utils/auth.js`, `frontend/vite.config.js`: runtime origin resolution, auth storage, TLS/proxy behavior, and `@` alias.
## Working Notes
- Run app commands from `backend/` or `frontend/`; there are no root-level npm or Python app scripts.
- Source comments and user-facing copy mix English and Chinese; preserve the surrounding language unless the task explicitly changes UX text.
- Ignore generated or local-runtime paths unless the task targets them: `frontend/node_modules/`, `backend/.venv/`, `backend/app/**/__pycache__/`, `.pytest_cache/`.
- Do not commit secrets or runtime data such as `backend/.env`, `backend/server_private.pem`, `backend/app.log`, `certs/key.pem`, uploaded files, avatars, or device backup data.
- Safe config references are `backend/.env_example` and `docker/.env.example`.
- `backend/requirements.txt` is UTF-16 LE with BOM; preserve that encoding if you edit it.
- The frontend dev server expects `../certs/cert.pem` and `../certs/key.pem` relative to `frontend/`; its proxy defaults to backend port `8000` while Vite runs on `3000`.
- Importing `backend/app/database/__init__.py` creates tables and may touch the configured database.
- Backend tests avoid MySQL by setting `DATABASE_URL` to a temporary SQLite file in `backend/tests/conftest.py`.
- Local storage keys already in use include `token`, `username`, `avatar`, and `app_lang`; preserve them.
## Build, Run, Lint, and Test Commands
### Frontend
Run from `frontend/`:
```sh
npm install
npm run dev
npm run build
npm run preview
npm run test:e2ee-vectors
```
- `npm run dev`: starts Vite on `0.0.0.0:3000`; HTTPS is enabled when root cert files exist.
- `npm run build`: primary frontend verification command.
- `npm run preview`: serves the built frontend locally.
- `npm run test:e2ee-vectors`: validates browser-side crypto protocol vectors.
- Node engine is `^20.19.0 || >=22.12.0`; no frontend lint script or single-spec test runner exists.
### Backend
Run from `backend/`:
```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- On Windows, activate with `.venv\Scripts\activate`.
- Startup normally needs `backend/.env` values such as `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `JWT_SECRET_KEY`, and `DB_ENCRYPTION_KEY`.
- Importing the app touches DB bootstrap, so call out env/database blockers clearly.
### Backend Tests
Run from `backend/`:
```sh
pytest
pytest tests/test_chat_manager.py
pytest tests/test_chat_manager.py::test_disconnect_device_only_closes_matching_socket
pytest tests/test_e2ee_service.py::test_ws_ticket_is_single_use
pytest tests/test_file_validation.py -k avatar
```
- Single-test patterns: `pytest tests/test_file.py::test_name` and `pytest tests/test_file.py::TestClass::test_name`.
- Tests are plain pytest functions plus shared fixtures in `backend/tests/conftest.py`; they use temporary SQLite/app-data paths instead of MySQL.
- For backend-only changes without a suitable test, at least sanity-check import/startup if envs are available.
### Docker
Run from the repo root:
```sh
cp docker/.env.example docker/.env
docker compose --env-file docker/.env up -d --build
docker compose --env-file docker/.env down
docker compose --env-file docker/.env down -v
```
- Default Compose brings up `mysql`, `backend`, and `frontend`; `my_project_deploy/docker-compose.yml` is for image deployment, not the normal dev loop.
### Lint and Format Status
- No repo-level configs were found for `ruff`, `black`, `isort`, `flake8`, `eslint`, `prettier`, `vitest`, or `playwright`.
- No dedicated lint command is configured in either app.
- Preserve existing formatting; do not add a new formatter, linter, or test framework unless the task asks for it.
## Code Style Guidelines
### General
- Keep changes narrow, especially in very large files like `frontend/src/views/ChatRoom.vue`.
- Follow existing app boundaries instead of creating new top-level folders or parallel abstractions.
- Prefer small helpers over duplicating inline logic.
- Preserve API contracts unless all consumers are updated in the same task.
- Keep secrets, tokens, decrypted content, and private keys out of logs, docs, fixtures, and commits.
### Imports
- Backend files usually group imports as stdlib, third-party, then local modules.
- Backend commonly uses relative imports such as `.manager` and `..database`; stay consistent within each file.
- Frontend files mostly use relative imports; `@/` is available but used sparingly.
- Vue files commonly use semicolons and compact import braces like `{ref, reactive}`; match local style.
- Do not mix multiple import styles in the same file without a clear reason.
### Formatting
- Python uses 4-space indentation.
- Vue templates, scripts, and styles use 2-space indentation.
- Keep logical blank lines between helpers, routes, computed state, and watcher blocks.
- Prefer concise comments only when a block is non-obvious.
- Match surrounding formatting instead of normalizing unrelated sections.
### Naming and Types
- Python functions, variables, and modules use `snake_case`; classes, dataclasses, Pydantic schemas, and SQLAlchemy models use `PascalCase`.
- Python already uses modern built-in generics and union syntax like `list[str]` and `str | None`; add type hints when they materially improve clarity.
- Frontend refs, helpers, and reactive state use `camelCase`; view/component files use `PascalCase.vue`; shared utility filenames are typically lowercase.
- Constants and env-derived settings use `UPPER_SNAKE_CASE`.
- Frontend is plain JavaScript, not TypeScript; prefer clear names and lightweight runtime guards.
### Backend Conventions
- Add HTTP endpoints in router modules, not directly in `backend/app/main.py`, unless the endpoint is truly app-global.
- Use `Depends(get_db)` for request-scoped DB sessions.
- Put reusable persistence logic in `backend/app/database/crud.py` before duplicating query code in routes.
- Reuse `backend/app/utils/encryption.py` for metadata, file, and transport encryption behavior.
- Mutation paths typically use `db.add(...)`, `db.commit()`, and `db.refresh(...)`; preserve that pattern.
- Prefer Pydantic validation so FastAPI returns consistent `422` responses for malformed input.
- Raise `HTTPException` for client-facing failures, use `log_event()`/`build_log_payload()` for new operational logs, and do not leak raw exceptions to clients.
### Frontend Conventions
- Use Vue 3 `<script setup>` for new or edited SFC logic unless the file already follows another style.
- Keep views in `frontend/src/views/` and reusable helpers in `frontend/src/utils/`.
- Follow the existing `ref`, `reactive`, `computed`, `watch`, `onMounted`, and `onUnmounted` patterns.
- Use `axios` for HTTP, native `WebSocket` for chat updates, and `ElMessage`/`ElMessageBox` for user-facing feedback.
- Use scoped styles for view-specific CSS and `:deep(...)` only for Element Plus internals.
- Preserve current storage keys and backend field names expected by the UI.
### Error Handling and Contracts
- Backend `detail` strings are part of the frontend contract, not throwaway text.
- `frontend/src/views/Login.vue` and `frontend/src/views/ChatRoom.vue` translate exact backend `detail` strings; update those maps if backend wording changes.
- Preserve websocket payload keys unless producer and consumer are both updated together: `to`, `chat_type`, `enc_key`, `ciphertext`, `nonce`, `tag`, `msg_type`.
- Keep relationship/group-access status values stable: `pending`, `accepted`, `rejected`, `cancelled`, `approved`, `expired`, and related derived states.
- Keep file upload limits, allowlists, path-traversal guards, session binding, token blacklist, and permission checks aligned unless the task explicitly changes security behavior.
### Tests and Verification
- Add or update the most targeted test available for the area you changed.
- Backend tests usually favor lightweight fakes/fixtures over full-stack integration unless the behavior requires it.
- Prefer `pytest path::test_name` over running the whole suite when iterating on focused backend work.
- For frontend changes, prefer `npm run build`; run `npm run test:e2ee-vectors` when touching browser crypto code.
- If backend API behavior changes, verify the consuming UI in `frontend/src/views/Login.vue` or `frontend/src/views/ChatRoom.vue` in the same task.
## Agent Checklist
- Confirm whether work belongs to `backend/`, `frontend/`, or both, and run commands from the correct subdirectory.
- Use git commands from the relevant subrepo only; root-level git commands will not work here.
- Run the most relevant verification command for the files you changed.
- Call out missing env vars, unavailable databases, or other verification blockers in your handoff.
- If you edit `backend/requirements.txt`, preserve UTF-16 LE with BOM.
