# E2EE v1 Freeze Sheet

This document freezes the phase 0 decisions that later phases depend on.

## Frozen implementation choices

- Authentication: short-lived access token + HttpOnly refresh session + `auth_sessions` + single-use `ws-ticket`.
- Protocols: private chat uses X3DH + Double Ratchet; group chat uses Sender Keys.
- Algorithms: X25519 + Ed25519 + HKDF + AES-256-GCM.
- Frontend secret storage: IndexedDB.
- Release policy: run the app as `e2ee_v1` only and cut over with fresh deployment data.
- Feature flags: `e2ee_private_enabled`, `e2ee_group_enabled`.

## Selected frontend crypto direction

- Preferred ratchet implementation: a mature Signal-compatible client library rather than custom ratchet code.
- Current freeze target: integrate a libsignal-class implementation for X3DH/Double Ratchet primitives and keep repo-owned code focused on persistence, prekey lifecycle, envelope packing, and UI state.

## Frozen table inventory for phase 2

- `devices`: per-device identity, ownership, lifecycle, last seen, revoke state.
- `device_signed_prekeys`: active and previous signed prekeys by device.
- `device_one_time_prekeys`: one-time prekeys with consumption tracking.
- `conversations_v2`: stable conversation identity for private pair key or `group_id`.
- `messages_v2`: message metadata only; never store new plaintext bodies.
- `message_payloads`: per-recipient encrypted envelopes.
- `message_deliveries`: server delivery, ack, and read tracking.
- `attachment_blobs_v2`: encrypted blob metadata only.
- `group_sender_key_epochs`: sender-key epoch metadata and rotation markers.
- `auth_sessions`: refresh session records, revocation, rotation, and device binding.
- `users`: add `session_version` and `e2ee_enabled`.

## Frozen API surface for phases 3-5

- Device/auth
  - `POST /api/e2ee/devices/bootstrap`
  - `GET /api/e2ee/devices`
  - `GET /api/e2ee/devices/me`
  - `POST /api/e2ee/devices/{device_id}/prekeys/refresh`
  - `POST /api/e2ee/devices/{device_id}/revoke`
  - `GET /api/e2ee/users/{user_id}/prekey-bundle`
  - `POST /api/e2ee/ws-ticket`
  - `WS /api/e2ee/ws?ticket=...`
- Private messaging
  - `GET /api/e2ee/conversations`
  - `GET /api/e2ee/inbox`
  - `GET /api/e2ee/conversations/{id}/messages`
- Attachments
  - `POST /api/e2ee/attachments/init`
  - `PUT /api/e2ee/attachments/{blob_id}`
  - `POST /api/e2ee/attachments/{blob_id}/complete`
  - `GET /api/e2ee/attachments/{blob_id}`

## Post-cutover policy

- The app now runs only on `e2ee_v1` message and attachment paths.
- Test/legacy data is disposable and should be dropped during release cutover instead of migrated.

## Conversation key rules

- Private conversation key format: deterministic ordered pair key `min(user_id_a,user_id_b):max(user_id_a,user_id_b)`.
- Group conversation key format: `group:{group_id}`.
- Frontend conversation caches must preserve the same identifiers across reconnects and device restarts.

## Minimal verification baseline

- Backend unit test runner: `pytest` from `backend/`.
- Initial unit baseline: file validation and config-safe pure helpers under `backend/tests/`.
- Protocol test vectors: reserve `backend/tests/protocol_vectors/` for X3DH, Double Ratchet, and Sender Key fixtures as phases 3-6 land.
- Phase 9 vector gate: run `npm run test:e2ee-vectors` from `frontend/` before release to validate Ed25519, X25519, HKDF-SHA256, and AES-256-GCM primitives.
- Manual smoke checklist:
  - login, logout, refresh, and unauthorized request rejection
  - private and group `e2ee_v1` send/receive, including inbox replay after reconnect
  - encrypted attachment upload/download success path plus validation failures
  - friend/group access updates over WebSocket
  - security headers present on frontend and backend responses

## Delivery order

- Milestone M1: finish phases 0-3.
- Milestone M2: finish phase 4 and declare private-text E2EE MVP.
- Milestone M3: finish phase 5 for encrypted attachments.
- Milestone M4: finish phases 6-7 for groups and multi-device UX.
- Milestone M5: finish phases 8-9 for legacy retirement and launch readiness.
