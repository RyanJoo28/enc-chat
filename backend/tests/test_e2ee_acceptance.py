import asyncio
import hashlib
import json
import uuid
from datetime import timedelta
from pathlib import Path

from app.chat.manager import manager as chat_manager
from app.database.models import (
    AuthSession,
    Device,
    DeviceOneTimePrekey,
    DeviceSignedPrekey,
    Friendship,
    Group,
    GroupMember,
    MessagePayload,
    MessageV2,
    PrivateChatAccess,
    User,
)
from app.e2ee.routes import bootstrap_device, revoke_device
from app.e2ee.schemas import DeviceBootstrapRequest, OneTimePrekeyInput, SignedPrekeyInput
from app.e2ee.service import (
    complete_attachment_blob,
    create_group_message,
    create_private_message,
    get_or_create_group_sender_key_epoch,
    init_attachment_blob,
    list_conversation_messages_for_device,
    list_inbox_for_device,
    claim_prekey_bundle,
    recall_message,
    revoke_device_for_user,
    store_attachment_blob_bytes,
    utcnow,
)
from app.user.dependencies import AuthContext


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, message: str):
        self.messages.append(message)

    async def close(self, code: int = 1000, reason: str | None = None):
        self.closed = True


class FakeClient:
    def __init__(self, host: str = "127.0.0.1"):
        self.host = host


class FakeRequest:
    def __init__(self, headers: dict | None = None):
        self.client = FakeClient()
        self.headers = headers or {"user-agent": "pytest"}


def _json_text(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _make_signal_envelope(ciphertext: str, *, sender_device_id: str, counter: int = 0) -> str:
    return json.dumps({
        "version": "e2ee_v1",
        "mode": "message",
        "sender_device_id": sender_device_id,
        "counter": counter,
        "nonce": "bm9uY2U=",
        "ciphertext": ciphertext,
    }, ensure_ascii=False, separators=(",", ":"))


def _make_group_envelope(ciphertext: str, *, sender_device_id: str, epoch: int = 1) -> str:
    return json.dumps({
        "version": "e2ee_v1",
        "mode": "group_sender_key",
        "sender_device_id": sender_device_id,
        "epoch": epoch,
        "nonce": "bm9uY2U=",
        "ciphertext": ciphertext,
    }, ensure_ascii=False, separators=(",", ":"))


def _create_user(db_session, username: str, *, password: str = "hashed-password") -> User:
    user = User(password=password, e2ee_enabled=True)
    user.username = username
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_private_access(db_session, user_a: User, user_b: User) -> None:
    low_id, high_id = sorted((user_a.id, user_b.id))
    db_session.add(Friendship(user_one_id=low_id, user_two_id=high_id))
    db_session.add(PrivateChatAccess(user_one_id=low_id, user_two_id=high_id, is_enabled=True))
    db_session.commit()


def _create_group(db_session, owner: User, members: list[User], *, name: str = "Test Group") -> Group:
    group = Group(owner_id=owner.id)
    group.name = name
    db_session.add(group)
    db_session.flush()
    all_members = {owner.id}
    all_members.update(member.id for member in members)
    for member_id in all_members:
        db_session.add(GroupMember(group_id=group.id, user_id=member_id))
    db_session.commit()
    db_session.refresh(group)
    return group


def _create_device(
        db_session,
        user: User,
        *,
        device_id: str,
        identity_key_public: str | None = None,
        signing_key_public: str | None = None,
        signed_prekey_public: str | None = None,
        signed_prekey_signature: str = "sig",
        one_time_prekeys: list[tuple[int, str]] | None = None,
) -> Device:
    device = Device(
        device_id=device_id,
        user_id=user.id,
        device_name=f"{device_id}-name",
        platform="pytest",
        identity_key_public=identity_key_public or _json_text(f"identity:{device_id}"),
        signing_key_public=signing_key_public or _json_text(f"signing:{device_id}"),
        registration_id=abs(hash(device_id)) % 2147483647 or 1,
        is_active=True,
    )
    db_session.add(device)
    db_session.flush()

    db_session.add(DeviceSignedPrekey(
        device_id=device.id,
        key_id=1,
        public_key=signed_prekey_public or _json_text(f"signed-prekey:{device_id}"),
        signature=signed_prekey_signature,
        is_active=True,
    ))
    for key_id, public_key in (one_time_prekeys or [(1, _json_text(f"otp:{device_id}:1"))]):
        db_session.add(DeviceOneTimePrekey(
            device_id=device.id,
            key_id=key_id,
            public_key=public_key,
            is_consumed=False,
        ))

    db_session.commit()
    db_session.refresh(device)
    return device


def _create_auth_session(db_session, user: User, device: Device) -> AuthSession:
    auth_session = AuthSession(
        session_id=str(uuid.uuid4()),
        user_id=user.id,
        device_id=device.id,
        refresh_token_hash=hashlib.sha256(f"refresh:{user.id}:{device.device_id}".encode("utf-8")).hexdigest(),
        session_family_id=str(uuid.uuid4()),
        user_session_version=user.session_version,
        status="active",
        last_used_at=utcnow(),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth_session)
    db_session.commit()
    db_session.refresh(auth_session)
    return auth_session


def _auth_context(user: User, auth_session: AuthSession, device: Device) -> AuthContext:
    return AuthContext(user=user, auth_session=auth_session, device=device, token_payload={})


def test_private_message_history_and_inbox_only_return_envelopes(db_session):
    plaintext = "server cannot decrypt this private body"
    alice = _create_user(db_session, "alice")
    bob = _create_user(db_session, "bob")
    _create_private_access(db_session, alice, bob)
    alice_device = _create_device(db_session, alice, device_id="alice-main")
    bob_device = _create_device(db_session, bob, device_id="bob-main")

    recipient_envelope = _make_signal_envelope("cHJpdmF0ZS1jaXBoZXJ0ZXh0", sender_device_id=alice_device.device_id)
    mirror_envelope = json.dumps({
        "version": "e2ee_v1",
        "mode": "local",
        "nonce": "bG9jYWwtbm9uY2U=",
        "ciphertext": "bG9jYWwtY2lwaGVydGV4dA==",
    }, ensure_ascii=False, separators=(",", ":"))

    result = create_private_message(
        db_session,
        sender=alice,
        sender_device=alice_device,
        target_user_id=bob.id,
        client_message_id="private-1",
        message_type="text",
        packets=[
            {
                "recipient_user_id": bob.id,
                "recipient_device_id": bob_device.device_id,
                "envelope_type": "signal",
                "envelope": recipient_envelope,
            },
            {
                "recipient_user_id": alice.id,
                "recipient_device_id": alice_device.device_id,
                "envelope_type": "local",
                "envelope": mirror_envelope,
            },
        ],
    )

    stored_payloads = db_session.query(MessagePayload).filter(MessagePayload.message_id == result["message"].id).all()
    assert stored_payloads
    assert all(plaintext not in payload.envelope for payload in stored_payloads)
    assert db_session.query(MessageV2).filter(MessageV2.id == result["message"].id).first().message_type == "text"

    history = list_conversation_messages_for_device(
        db_session,
        current_user_id=bob.id,
        device=bob_device,
        conversation_id=result["conversation"].id,
    )
    inbox = list_inbox_for_device(db_session, current_user_id=bob.id, device=bob_device)

    assert len(history) == 1
    assert len(inbox) == 1
    assert history[0]["envelope"] == recipient_envelope
    assert inbox[0]["envelope"] == recipient_envelope
    assert "content" not in history[0]
    assert "content" not in inbox[0]
    assert plaintext not in json.dumps(history[0], ensure_ascii=False)
    assert plaintext not in json.dumps(inbox[0], ensure_ascii=False)


def test_group_regression_recall_and_history_remain_envelope_only(db_session):
    plaintext = "group body hidden from the server"
    alice = _create_user(db_session, "group-alice")
    bob = _create_user(db_session, "group-bob")
    carol = _create_user(db_session, "group-carol")
    alice_device = _create_device(db_session, alice, device_id="group-alice-main")
    bob_device = _create_device(db_session, bob, device_id="group-bob-main")
    carol_device = _create_device(db_session, carol, device_id="group-carol-main")
    group = _create_group(db_session, alice, [bob, carol])
    epoch = get_or_create_group_sender_key_epoch(db_session, group.id, alice.id)

    bob_envelope = _make_group_envelope("Z3JvdXAtYm9iLWNpcGhlcg==", sender_device_id=alice_device.device_id, epoch=epoch.epoch)
    carol_envelope = _make_group_envelope("Z3JvdXAtY2Fyb2wtY2lwaGVy", sender_device_id=alice_device.device_id, epoch=epoch.epoch)
    alice_envelope = _make_group_envelope("Z3JvdXAtYWxpY2UtY2lwaGVy", sender_device_id=alice_device.device_id, epoch=epoch.epoch)

    result = create_group_message(
        db_session,
        sender=alice,
        sender_device=alice_device,
        group_id=group.id,
        group_epoch=epoch.epoch,
        client_message_id="group-1",
        message_type="text",
        packets=[
            {
                "recipient_user_id": bob.id,
                "recipient_device_id": bob_device.device_id,
                "envelope_type": "group_sender_key",
                "envelope": bob_envelope,
            },
            {
                "recipient_user_id": carol.id,
                "recipient_device_id": carol_device.device_id,
                "envelope_type": "group_sender_key",
                "envelope": carol_envelope,
            },
            {
                "recipient_user_id": alice.id,
                "recipient_device_id": alice_device.device_id,
                "envelope_type": "group_sender_key",
                "envelope": alice_envelope,
            },
        ],
    )

    initial_history = list_conversation_messages_for_device(
        db_session,
        current_user_id=bob.id,
        device=bob_device,
        conversation_id=result["conversation"].id,
    )
    assert len(initial_history) == 1
    assert initial_history[0]["envelope"] == bob_envelope
    assert "content" not in initial_history[0]
    assert plaintext not in json.dumps(initial_history[0], ensure_ascii=False)

    recall_message(db_session, current_user_id=alice.id, message_id=result["message"].id)
    recalled_history = list_conversation_messages_for_device(
        db_session,
        current_user_id=bob.id,
        device=bob_device,
        conversation_id=result["conversation"].id,
    )
    assert recalled_history[0]["is_recalled"] is True
    assert recalled_history[0]["envelope"] == bob_envelope
    assert plaintext not in json.dumps(recalled_history[0], ensure_ascii=False)


def test_attachment_storage_leakage_only_exposes_ciphertext(db_session):
    plaintext = b"top secret attachment body"
    ciphertext = b"cipher::top-secret-blob::v1"
    user = _create_user(db_session, "attachment-owner")
    device = _create_device(db_session, user, device_id="attachment-device")
    blob = init_attachment_blob(
        db_session,
        current_user=user,
        current_device=device,
        mime_type="application/octet-stream",
        ciphertext_size=len(ciphertext),
        ciphertext_sha256=hashlib.sha256(ciphertext).hexdigest(),
    )

    store_attachment_blob_bytes(db_session, blob=blob, ciphertext=ciphertext)
    complete_attachment_blob(db_session, blob=blob, ciphertext_sha256=hashlib.sha256(ciphertext).hexdigest())

    stored_bytes = Path(blob.storage_path).read_bytes()
    assert stored_bytes == ciphertext
    assert plaintext not in stored_bytes
    assert b"top secret attachment body" not in stored_bytes


def test_revoke_device_route_revokes_sessions_rotates_group_epoch_and_disconnects_socket(db_session):
    alice = _create_user(db_session, "revoke-alice")
    bob = _create_user(db_session, "revoke-bob")
    alice_primary = _create_device(db_session, alice, device_id="alice-primary")
    alice_secondary = _create_device(db_session, alice, device_id="alice-secondary")
    bob_device = _create_device(db_session, bob, device_id="bob-main")
    primary_session = _create_auth_session(db_session, alice, alice_primary)
    secondary_session = _create_auth_session(db_session, alice, alice_secondary)
    group = _create_group(db_session, alice, [bob], name="Revoke Group")
    original_epoch = get_or_create_group_sender_key_epoch(db_session, group.id, alice.id)

    actor_socket = FakeWebSocket()
    revoked_socket = FakeWebSocket()
    peer_socket = FakeWebSocket()

    async def connect_sockets():
        await chat_manager.connect(alice.id, actor_socket, alice_primary.device_id)
        await chat_manager.connect(alice.id, revoked_socket, alice_secondary.device_id)
        await chat_manager.connect(bob.id, peer_socket, bob_device.device_id)

    asyncio.run(connect_sockets())

    response = asyncio.run(revoke_device(
        device_id=alice_secondary.device_id,
        db=db_session,
        auth_context=_auth_context(alice, primary_session, alice_primary),
    ))

    db_session.refresh(alice_secondary)
    db_session.refresh(secondary_session)
    next_epoch = get_or_create_group_sender_key_epoch(db_session, group.id, alice.id)

    assert response["active_device_count"] == 1
    assert response["revoked_session_count"] == 1
    assert response["rotated_group_ids"] == [group.id]
    assert alice_secondary.is_active is False
    assert alice_secondary.revoked_at is not None
    assert secondary_session.status == "revoked"
    assert revoked_socket.closed is True
    assert next_epoch.epoch == original_epoch.epoch + 1

    actor_payloads = [json.loads(message) for message in actor_socket.messages if message.startswith("{")]
    peer_payloads = [json.loads(message) for message in peer_socket.messages if message.startswith("{")]
    assert any(payload.get("type") == "device.revoked" and payload.get("device_id") == alice_secondary.device_id for payload in actor_payloads)
    assert any(payload.get("type") == "device.revoked" and payload.get("device_id") == alice_secondary.device_id for payload in peer_payloads)
    assert any(payload.get("type") == "group_epoch_changed" and payload.get("group_id") == group.id for payload in actor_payloads)
    assert any(payload.get("type") == "group_epoch_changed" and payload.get("group_id") == group.id for payload in peer_payloads)


def test_identity_change_bootstrap_replaces_existing_device_identity_and_prekey_bundle(db_session):
    alice = _create_user(db_session, "identity-alice")
    bob = _create_user(db_session, "identity-bob")
    _create_private_access(db_session, alice, bob)
    alice_device = _create_device(
        db_session,
        alice,
        device_id="identity-device",
        identity_key_public=_json_text("identity-old"),
        signing_key_public=_json_text("signing-old"),
        signed_prekey_public=_json_text("signed-prekey-old"),
        one_time_prekeys=[(1, _json_text("otp-old-1"))],
    )
    alice_session = _create_auth_session(db_session, alice, alice_device)

    payload = DeviceBootstrapRequest(
        device_id=alice_device.device_id,
        device_name="identity-device-name",
        platform="pytest",
        identity_key_public=_json_text("identity-new"),
        signing_key_public=_json_text("signing-new"),
        registration_id=alice_device.registration_id,
        signed_prekey=SignedPrekeyInput(
            key_id=9,
            public_key=_json_text("signed-prekey-new"),
            signature="sig-new",
        ),
        one_time_prekeys=[
            OneTimePrekeyInput(key_id=10, public_key=_json_text("otp-new-10")),
            OneTimePrekeyInput(key_id=11, public_key=_json_text("otp-new-11")),
        ],
    )

    bootstrap_handler = getattr(bootstrap_device, "__wrapped__", bootstrap_device)
    result = asyncio.run(bootstrap_handler(
        request=FakeRequest(),
        payload=payload,
        db=db_session,
        auth_context=_auth_context(alice, alice_session, alice_device),
    ))
    db_session.refresh(alice_device)

    bundle = claim_prekey_bundle(db_session, alice.id, consume_one_time_prekeys=False)
    asserted_bundle = next(device for device in bundle["devices"] if device["device_id"] == alice_device.device_id)

    assert result["active_device_count"] == 1
    assert result["device"]["device_id"] == alice_device.device_id
    assert result["device"]["identity_key_public"] == _json_text("identity-new")
    assert alice_device.identity_key_public == _json_text("identity-new")
    assert asserted_bundle["identity_key_public"] == _json_text("identity-new")
    assert asserted_bundle["signed_prekey"]["key_id"] == 9


def test_revoke_device_service_is_idempotent(db_session):
    user = _create_user(db_session, "service-revoke")
    device = _create_device(db_session, user, device_id="service-device")
    _create_auth_session(db_session, user, device)

    first = revoke_device_for_user(db_session, user_id=user.id, device_public_id=device.device_id)
    second = revoke_device_for_user(db_session, user_id=user.id, device_public_id=device.device_id)

    assert first["active_device_count"] == 0
    assert first["revoked_session_count"] == 1
    assert second["active_device_count"] == 0
    assert second["revoked_session_count"] == 0
