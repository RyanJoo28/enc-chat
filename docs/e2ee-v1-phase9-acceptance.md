# E2EE v1 Phase 9 Acceptance

This document is the launch-readiness checklist for proving that new chat traffic is genuinely end-to-end encrypted.

## Acceptance target

- Remove any server-side message-body decryption path without breaking new `e2ee_v1` traffic.
- Keep history and inbox APIs envelope-only for new messages.
- Ensure database leakage cannot recover new message bodies.
- Ensure attachment storage leakage cannot recover new attachment bodies.

## Automated checks

Run from `backend/`:

```sh
pytest tests/test_chat_manager.py tests/test_e2ee_service.py tests/test_e2ee_acceptance.py
```

Run from `frontend/`:

```sh
npm run test:e2ee-vectors
```

What these checks cover:

- `F9-01` protocol vectors for Ed25519, X25519, HKDF-SHA256, and AES-256-GCM.
- `F9-02` private chat, group chat, recall metadata, inbox, and attachment regression.
- `F9-03` database leakage drill by asserting `messages_v2` + `message_payloads` never expose plaintext bodies.
- `F9-04` attachment leakage drill by asserting stored blobs remain ciphertext-only.
- `F9-05` WebSocket ticket replay prevention through single-use and expiry tests.
- `F9-06` multi-device revocation and identity replacement tests.

## Manual attack drills

### Database leakage drill

1. Send fresh private and group `e2ee_v1` messages.
2. Inspect `messages_v2` and `message_payloads` directly.
3. Verify that:
   - `messages_v2` contains metadata only.
   - `message_payloads.envelope` contains only encrypted envelopes.
   - No plaintext message body appears in SQL dumps, ORM queries, or history responses.

Expected result: the server can identify sender, recipient device, timestamps, delivery state, and recall state, but not recover new plaintext bodies.

### Attachment leakage drill

1. Upload a fresh encrypted attachment through the E2EE attachment flow.
2. Inspect the file under `backend/uploaded_files_v2/` or the configured `E2EE_ATTACHMENT_DIR`.
3. Verify that:
   - raw stored bytes match uploaded ciphertext bytes,
   - plaintext file magic and plaintext strings do not appear,
   - download endpoints still return ciphertext only.

Expected result: storage compromise yields blob metadata and ciphertext, not readable attachment content.

### WebSocket replay drill

1. Mint a `ws-ticket`.
2. Connect once with `WS /api/e2ee/ws?ticket=...`.
3. Attempt a second connection with the same ticket.

Expected result: first connect succeeds, replayed ticket is rejected.

### Multi-device revoke drill

1. Bind two devices to the same account.
2. Revoke the secondary device using `POST /api/e2ee/devices/{device_id}/revoke` from the surviving device.
3. Verify that:
   - the revoked device loses live WebSocket access,
   - bound refresh sessions are revoked,
   - group sender-key epochs rotate for affected groups,
   - new message fanout no longer targets the revoked device.

## Performance pressure plan

Collect at least these measurements before launch:

- session pull latency for `GET /api/e2ee/users/{user_id}/prekey-bundle` and `GET /api/e2ee/groups/{group_id}/member-devices`,
- offline inbox fetch latency for `GET /api/e2ee/inbox` with 50/100/200 pending items,
- group fanout write latency for `create_group_message` at 10/50/100 recipient devices,
- attachment upload + complete latency for 1 MB, 5 MB, and 20 MB ciphertext blobs.

Record:

- p50 / p95 latency,
- database row growth per message,
- websocket broadcast backlog under group fanout,
- CPU and memory for backend + database.

## Gray rollout and rollback

### Gray rollout

1. Deploy backend with only `e2ee_v1` routes enabled.
2. Start with a fresh database or disposable staging copy.
3. Validate protocol vectors and acceptance tests.
4. Smoke-test private chat, group chat, attachments, recall, reconnect, and device revocation with two real browsers.
5. Expand traffic only after envelope-only history and ciphertext-only storage are confirmed.

### Rollback

1. Stop new traffic to the candidate deployment.
2. Preserve logs and database snapshots for forensic review.
3. Roll back to the last known-good image and configuration bundle.
4. Re-run protocol vectors and the backend acceptance suite before reopening traffic.

Because the release policy is fresh-cutover `e2ee_v1` only, rollback is image/config based rather than legacy data migration based.

## Exit criteria

- New private and group chats still work after removing server-side plaintext decryption logic.
- Inbox/history responses for new traffic remain envelope-only.
- Database dumps cannot recover new message bodies.
- Attachment storage dumps cannot recover new attachment bodies.
- WebSocket tickets are single-use and expire.
- Device revocation invalidates live sessions and rotates affected group epochs.
