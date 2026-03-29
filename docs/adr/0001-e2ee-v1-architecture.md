# ADR 0001: E2EE v1 Re-architecture Baseline

- Status: Accepted
- Date: 2026-03-23

## Context

The current chat stack encrypts payloads to the server, decrypts them on the backend, stores decrypted message bodies in a server-readable form, and authenticates WebSocket and file access with JWTs that can appear in browser storage or URLs. This blocks any claim of true end-to-end encryption and leaves several high-priority security issues independent from the protocol redesign.

## Decision

### Authentication model

- Use short-lived access tokens for API authorization.
- Introduce HttpOnly refresh sessions backed by `auth_sessions`.
- Replace URL-based WebSocket JWT auth with single-use `ws-ticket` exchange.
- Device registration, refresh rotation, and revocation are part of the server-owned auth surface.
- Device revocation must also invalidate bound refresh sessions, disconnect live WebSocket sessions for that device, and rotate affected group sender-key epochs.

### Device model

- Each browser or app instance is a first-class device.
- Each device owns its own identity key material and signed prekeys.
- Frontend device secrets live in IndexedDB and are reused across restarts until the device is explicitly revoked.

### Protocol model

- Private chat uses X3DH for initial session setup.
- Private chat uses Double Ratchet for ongoing message encryption.
- Group chat uses Sender Keys with explicit epoch rotation when membership changes.
- Do not hand-write a ratchet implementation; integrate a mature Signal-compatible library and keep custom code limited to storage, envelope formatting, and API glue.

### Cryptographic baseline

- Key agreement: X25519.
- Signing: Ed25519.
- Key derivation: HKDF.
- Content encryption: AES-256-GCM.

### Conversation identity rules

- Private `conversations_v2` rows use a stable ordered pair key derived from the two user IDs.
- Group `conversations_v2` rows are bound directly to `group_id`.

### Cutover strategy

- New messages move to `e2ee_v1` immediately once a flow is ready.
- The current release track assumes test data is disposable and uses a fresh cutover instead of preserving old server-readable chat history.
- Legacy paths are removed from the runtime app once the `e2ee_v1` flow is stable.

### Rollout order

- Phase 0: freeze architecture and interfaces.
- Phase 1: close independent security gaps.
- Phase 2: add migration-backed database foundation.
- Phase 3-4: deliver device identity, new auth channel, and private-text E2EE MVP.
- Phase 5-7: add encrypted attachments, group chat, and long-term device UX.
- Phase 8-9: retire legacy paths and run final validation.

## Consequences

- The backend loses access to new message plaintext and can no longer generate authoritative plaintext previews.
- IndexedDB becomes security-critical client storage and must be versioned carefully.
- The release build targets the `e2ee_v1` tables and APIs as the only supported runtime path.
- Backend and frontend must treat exact error/detail strings as compatibility contracts during the transition.
