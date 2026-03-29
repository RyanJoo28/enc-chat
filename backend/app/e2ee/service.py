import hashlib
import json
import re
import secrets
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import crud
from ..database.models import (
    AttachmentBlobV2,
    AuthSession,
    ConversationV2,
    Device,
    DeviceOneTimePrekey,
    DeviceSignedPrekey,
    Group,
    GroupMember,
    GroupSenderKeyEpoch,
    MessageDelivery,
    MessagePayload,
    MessageV2,
    User,
)
from ..settings import (
    CORS_ALLOWED_ORIGIN_REGEX,
    CORS_ALLOWED_ORIGINS,
    E2EE_ATTACHMENT_DIR,
    E2EE_ATTACHMENT_MAX_BYTES,
    E2EE_ATTACHMENT_UPLOAD_TTL_MINUTES,
    WS_MAX_MESSAGES_PER_MINUTE,
    WS_TICKET_TTL_SECONDS,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def naive_utcnow() -> datetime:
    return utcnow().replace(tzinfo=None)


def serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _serialize_last_message_meta(db: Session, conversation_id: int) -> dict:
    row = db.query(MessageV2, User).join(
        User,
        User.id == MessageV2.sender_user_id,
    ).filter(
        MessageV2.conversation_id == conversation_id,
    ).order_by(
        MessageV2.created_at.desc(),
        MessageV2.id.desc(),
    ).first()
    if row is None:
        return {
            "last_message_id": None,
            "last_message_is_recalled": False,
            "last_message_sender_user_id": None,
            "last_message_sender_username": None,
            "last_message_sender_avatar": None,
            "last_message_type": None,
            "last_message_created_at": None,
        }

    message, sender = row
    return {
        "last_message_id": message.id,
        "last_message_is_recalled": bool(message.is_recalled),
        "last_message_sender_user_id": message.sender_user_id,
        "last_message_sender_username": sender.username if sender else None,
        "last_message_sender_avatar": sender.avatar if sender else None,
        "last_message_type": message.message_type,
        "last_message_created_at": serialize_datetime(message.created_at),
    }


E2EE_ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_E2EE_ATTACHMENT_MIME_PREFIXES = ("image/", "text/")
ALLOWED_E2EE_ATTACHMENT_MIME_TYPES = {
    "application/pdf",
    "application/zip",
    "application/octet-stream",
}


def _attachment_upload_expiry() -> datetime:
    return naive_utcnow() + timedelta(minutes=E2EE_ATTACHMENT_UPLOAD_TTL_MINUTES)


def _attachment_storage_path(blob_id: str) -> Path:
    return E2EE_ATTACHMENT_DIR / f"{blob_id}.bin"


def _is_allowed_attachment_mime(mime_type: str) -> bool:
    return mime_type.startswith(ALLOWED_E2EE_ATTACHMENT_MIME_PREFIXES) or mime_type in ALLOWED_E2EE_ATTACHMENT_MIME_TYPES


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def is_allowed_ws_origin(origin: str | None) -> bool:
    if not origin:
        return False

    if origin in CORS_ALLOWED_ORIGINS:
        return True

    if CORS_ALLOWED_ORIGIN_REGEX:
        return re.fullmatch(CORS_ALLOWED_ORIGIN_REGEX, origin) is not None

    return False


def rate_limit_window_exceeded(message_timestamps: deque[float], current_ts: float) -> bool:
    window_start = current_ts - 60.0
    while message_timestamps and message_timestamps[0] < window_start:
        message_timestamps.popleft()

    if len(message_timestamps) >= WS_MAX_MESSAGES_PER_MINUTE:
        return True

    message_timestamps.append(current_ts)
    return False


@dataclass
class WsTicket:
    token: str
    user_id: int
    session_public_id: str
    device_public_id: str
    expires_at: datetime


class WsTicketStore:
    def __init__(self):
        self._tickets: dict[str, WsTicket] = {}
        self._lock = threading.Lock()

    def create(self, *, user_id: int, session_public_id: str, device_public_id: str) -> WsTicket:
        ticket = WsTicket(
            token=secrets.token_urlsafe(32),
            user_id=user_id,
            session_public_id=session_public_id,
            device_public_id=device_public_id,
            expires_at=utcnow() + timedelta(seconds=WS_TICKET_TTL_SECONDS),
        )
        with self._lock:
            self._purge_locked()
            self._tickets[ticket.token] = ticket
        return ticket

    def consume(self, token: str) -> WsTicket | None:
        with self._lock:
            self._purge_locked()
            return self._tickets.pop(token, None)

    def _purge_locked(self) -> None:
        now = utcnow()
        expired_tokens = [token for token, ticket in self._tickets.items() if ticket.expires_at <= now]
        for token in expired_tokens:
            self._tickets.pop(token, None)


ws_ticket_store = WsTicketStore()


def get_device_for_user(db: Session, user_id: int, device_public_id: str) -> Device | None:
    return db.query(Device).filter(
        Device.user_id == user_id,
        Device.device_id == device_public_id,
    ).first()


def get_active_device_for_user(db: Session, user_id: int, device_public_id: str) -> Device | None:
    return db.query(Device).filter(
        Device.user_id == user_id,
        Device.device_id == device_public_id,
        Device.is_active.is_(True),
        Device.revoked_at.is_(None),
    ).first()


def list_active_devices_for_user(db: Session, user_id: int) -> list[Device]:
    return db.query(Device).filter(
        Device.user_id == user_id,
        Device.is_active.is_(True),
        Device.revoked_at.is_(None),
    ).order_by(Device.created_at.asc(), Device.id.asc()).all()


def list_devices_for_user(db: Session, user_id: int) -> list[Device]:
    return db.query(Device).filter(
        Device.user_id == user_id,
    ).order_by(Device.created_at.asc(), Device.id.asc()).all()


def serialize_device_summary(db: Session, device: Device) -> dict:
    signed_prekey = db.query(DeviceSignedPrekey).filter(
        DeviceSignedPrekey.device_id == device.id,
        DeviceSignedPrekey.is_active.is_(True),
    ).order_by(DeviceSignedPrekey.published_at.desc(), DeviceSignedPrekey.id.desc()).first()

    one_time_prekey_count = db.query(DeviceOneTimePrekey).filter(
        DeviceOneTimePrekey.device_id == device.id,
        DeviceOneTimePrekey.is_consumed.is_(False),
    ).count()

    return {
        "device_id": device.device_id,
        "device_name": device.device_name,
        "platform": device.platform,
        "registration_id": device.registration_id,
        "identity_key_curve": device.identity_key_curve,
        "identity_key_public": device.identity_key_public,
        "signing_key_curve": device.signing_key_curve,
        "signing_key_public": device.signing_key_public,
        "signed_prekey": {
            "key_id": signed_prekey.key_id,
            "public_key": signed_prekey.public_key,
            "signature": signed_prekey.signature,
            "published_at": serialize_datetime(signed_prekey.published_at),
        } if signed_prekey else None,
        "one_time_prekey_count": one_time_prekey_count,
        "is_active": device.is_active,
        "created_at": serialize_datetime(device.created_at),
        "last_seen_at": serialize_datetime(device.last_seen_at),
        "revoked_at": serialize_datetime(device.revoked_at),
    }


def serialize_owned_device_summary(db: Session, device: Device, *, current_device_public_id: str | None = None) -> dict:
    active_session_count = db.query(AuthSession).filter(
        AuthSession.user_id == device.user_id,
        AuthSession.device_id == device.id,
        AuthSession.status == "active",
    ).count()
    return {
        **serialize_device_summary(db, device),
        "is_current": bool(current_device_public_id and current_device_public_id == device.device_id),
        "active_session_count": active_session_count,
    }


def revoke_device_for_user(
        db: Session,
        *,
        user_id: int,
        device_public_id: str,
) -> dict:
    device = get_device_for_user(db, user_id, device_public_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")

    group_ids = {
        group_id
        for group_id, in db.query(GroupMember.group_id).filter(GroupMember.user_id == user_id).all()
    }

    if device.revoked_at is not None or not device.is_active:
        return {
            "did_revoke": False,
            "device": device,
            "active_device_count": len(list_active_devices_for_user(db, user_id)),
            "revoked_session_count": 0,
            "group_ids": sorted(group_ids),
        }

    now = naive_utcnow()
    device.is_active = False
    device.revoked_at = now

    db.query(DeviceSignedPrekey).filter(
        DeviceSignedPrekey.device_id == device.id,
        DeviceSignedPrekey.is_active.is_(True),
    ).update(
        {
            DeviceSignedPrekey.is_active: False,
            DeviceSignedPrekey.replaced_at: now,
        },
        synchronize_session=False,
    )
    db.query(DeviceOneTimePrekey).filter(
        DeviceOneTimePrekey.device_id == device.id,
        DeviceOneTimePrekey.is_consumed.is_(False),
    ).update(
        {
            DeviceOneTimePrekey.is_consumed: True,
            DeviceOneTimePrekey.consumed_at: now,
        },
        synchronize_session=False,
    )

    revoked_session_count = 0
    session_now = utcnow()
    active_sessions = db.query(AuthSession).filter(
        AuthSession.user_id == user_id,
        AuthSession.device_id == device.id,
        AuthSession.status == "active",
    ).all()
    for auth_session in active_sessions:
        auth_session.status = "revoked"
        auth_session.revoked_at = session_now
        auth_session.last_used_at = session_now
        revoked_session_count += 1

    db.commit()
    db.refresh(device)
    return {
        "did_revoke": True,
        "device": device,
        "active_device_count": len(list_active_devices_for_user(db, user_id)),
        "revoked_session_count": revoked_session_count,
        "group_ids": sorted(group_ids),
    }


def replace_device_keys(
        db: Session,
        *,
        device: Device,
        signed_prekey,
        one_time_prekeys: list,
) -> None:
    now = naive_utcnow()
    db.query(DeviceSignedPrekey).filter(
        DeviceSignedPrekey.device_id == device.id,
        DeviceSignedPrekey.is_active.is_(True),
    ).update(
        {
            DeviceSignedPrekey.is_active: False,
            DeviceSignedPrekey.replaced_at: now,
        },
        synchronize_session=False,
    )

    existing_signed_prekey = db.query(DeviceSignedPrekey).filter(
        DeviceSignedPrekey.device_id == device.id,
        DeviceSignedPrekey.key_id == signed_prekey.key_id,
    ).first()

    if existing_signed_prekey is None:
        db.add(DeviceSignedPrekey(
            device_id=device.id,
            key_id=signed_prekey.key_id,
            public_key=signed_prekey.public_key,
            signature=signed_prekey.signature,
            is_active=True,
            published_at=now,
            replaced_at=None,
        ))
    else:
        existing_signed_prekey.public_key = signed_prekey.public_key
        existing_signed_prekey.signature = signed_prekey.signature
        existing_signed_prekey.is_active = True
        existing_signed_prekey.published_at = now
        existing_signed_prekey.replaced_at = None

    db.query(DeviceOneTimePrekey).filter(DeviceOneTimePrekey.device_id == device.id).delete(synchronize_session=False)
    for prekey in one_time_prekeys:
        db.add(DeviceOneTimePrekey(
            device_id=device.id,
            key_id=prekey.key_id,
            public_key=prekey.public_key,
            is_consumed=False,
            published_at=now,
        ))


def append_device_one_time_prekeys(db: Session, *, device: Device, one_time_prekeys: list) -> int:
    if not one_time_prekeys:
        return 0

    existing_key_ids = {
        key_id
        for key_id, in db.query(DeviceOneTimePrekey.key_id).filter(DeviceOneTimePrekey.device_id == device.id).all()
    }

    added_count = 0
    now = naive_utcnow()
    for prekey in one_time_prekeys:
        if prekey.key_id in existing_key_ids:
            continue
        db.add(DeviceOneTimePrekey(
            device_id=device.id,
            key_id=prekey.key_id,
            public_key=prekey.public_key,
            is_consumed=False,
            published_at=now,
        ))
        existing_key_ids.add(prekey.key_id)
        added_count += 1

    return added_count


def replace_active_signed_prekey(db: Session, *, device: Device, signed_prekey) -> None:
    now = naive_utcnow()
    db.query(DeviceSignedPrekey).filter(
        DeviceSignedPrekey.device_id == device.id,
        DeviceSignedPrekey.is_active.is_(True),
    ).update(
        {
            DeviceSignedPrekey.is_active: False,
            DeviceSignedPrekey.replaced_at: now,
        },
        synchronize_session=False,
    )

    existing_signed_prekey = db.query(DeviceSignedPrekey).filter(
        DeviceSignedPrekey.device_id == device.id,
        DeviceSignedPrekey.key_id == signed_prekey.key_id,
    ).first()

    if existing_signed_prekey is None:
        db.add(DeviceSignedPrekey(
            device_id=device.id,
            key_id=signed_prekey.key_id,
            public_key=signed_prekey.public_key,
            signature=signed_prekey.signature,
            is_active=True,
            published_at=now,
            replaced_at=None,
        ))
    else:
        existing_signed_prekey.public_key = signed_prekey.public_key
        existing_signed_prekey.signature = signed_prekey.signature
        existing_signed_prekey.is_active = True
        existing_signed_prekey.published_at = now
        existing_signed_prekey.replaced_at = None


def claim_prekey_bundle(
        db: Session,
        target_user_id: int,
        *,
        consume_one_time_prekeys: bool = True,
        device_public_ids: set[str] | None = None,
) -> dict:
    user = db.query(User).filter(User.id == target_user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标用户不存在")

    devices_payload = []
    active_devices = list_active_devices_for_user(db, target_user_id)
    if device_public_ids:
        active_devices = [device for device in active_devices if device.device_id in device_public_ids]
    for device in active_devices:
        bundle_payload = _claim_device_bundle_payload(db, device) if consume_one_time_prekeys else _peek_device_bundle_payload(db, device)
        if bundle_payload is not None:
            devices_payload.append(bundle_payload)

    if consume_one_time_prekeys:
        db.commit()
    if active_devices and not devices_payload:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="目标用户设备尚未准备好建立 E2EE 会话")

    return {
        "user_id": user.id,
        "devices": devices_payload,
    }


def _claim_device_bundle_payload(db: Session, device: Device) -> dict | None:
    signed_prekey = db.query(DeviceSignedPrekey).filter(
        DeviceSignedPrekey.device_id == device.id,
        DeviceSignedPrekey.is_active.is_(True),
    ).order_by(DeviceSignedPrekey.published_at.desc(), DeviceSignedPrekey.id.desc()).first()
    if signed_prekey is None:
        return None

    one_time_prekey = db.query(DeviceOneTimePrekey).filter(
        DeviceOneTimePrekey.device_id == device.id,
        DeviceOneTimePrekey.is_consumed.is_(False),
    ).order_by(DeviceOneTimePrekey.published_at.asc(), DeviceOneTimePrekey.id.asc()).with_for_update().first()

    now = naive_utcnow()
    if one_time_prekey is not None:
        one_time_prekey.is_consumed = True
        one_time_prekey.consumed_at = now

    return {
        "device_id": device.device_id,
        "registration_id": device.registration_id,
        "identity_key_curve": device.identity_key_curve,
        "identity_key_public": device.identity_key_public,
        "signing_key_curve": device.signing_key_curve,
        "signing_key_public": device.signing_key_public,
        "signed_prekey": {
            "key_id": signed_prekey.key_id,
            "public_key": signed_prekey.public_key,
            "signature": signed_prekey.signature,
        },
        "one_time_prekey": {
            "key_id": one_time_prekey.key_id,
            "public_key": one_time_prekey.public_key,
        } if one_time_prekey else None,
    }


def _peek_device_bundle_payload(db: Session, device: Device) -> dict | None:
    signed_prekey = db.query(DeviceSignedPrekey).filter(
        DeviceSignedPrekey.device_id == device.id,
        DeviceSignedPrekey.is_active.is_(True),
    ).order_by(DeviceSignedPrekey.published_at.desc(), DeviceSignedPrekey.id.desc()).first()
    if signed_prekey is None:
        return None

    one_time_prekey = db.query(DeviceOneTimePrekey).filter(
        DeviceOneTimePrekey.device_id == device.id,
        DeviceOneTimePrekey.is_consumed.is_(False),
    ).order_by(DeviceOneTimePrekey.published_at.asc(), DeviceOneTimePrekey.id.asc()).first()

    return {
        "device_id": device.device_id,
        "registration_id": device.registration_id,
        "identity_key_curve": device.identity_key_curve,
        "identity_key_public": device.identity_key_public,
        "signing_key_curve": device.signing_key_curve,
        "signing_key_public": device.signing_key_public,
        "signed_prekey": {
            "key_id": signed_prekey.key_id,
            "public_key": signed_prekey.public_key,
            "signature": signed_prekey.signature,
        },
        "one_time_prekey": {
            "key_id": one_time_prekey.key_id,
            "public_key": one_time_prekey.public_key,
        } if one_time_prekey else None,
    }


def get_group_member_devices(
        db: Session,
        *,
        group_id: int,
        current_user_id: int,
        consume_one_time_prekeys: bool = False,
        target_user_id: int | None = None,
        device_public_ids: set[str] | None = None,
) -> dict:
    group = crud.get_group(db, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="群组不存在")

    member_ids = crud.get_group_members(db, group_id)
    if current_user_id not in member_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该群组")

    conversation = get_or_create_group_conversation(db, group_id)
    epoch = get_or_create_group_sender_key_epoch(db, group_id)

    members_payload = []
    for member in crud.get_group_members_detailed(db, group_id):
        if target_user_id is not None and member.id != target_user_id:
            continue

        device_payloads = []
        for device in list_active_devices_for_user(db, member.id):
            if device_public_ids and device.device_id not in device_public_ids:
                continue

            bundle_payload = _claim_device_bundle_payload(db, device) if consume_one_time_prekeys else _peek_device_bundle_payload(db, device)
            if bundle_payload is not None:
                device_payloads.append(bundle_payload)

        members_payload.append({
            "user_id": member.id,
            "username": member.username,
            "avatar": member.avatar,
            "devices": device_payloads,
        })

    if consume_one_time_prekeys:
        db.commit()

    return {
        "group_id": group.id,
        "conversation_id": conversation.id,
        "conversation_key": conversation.conversation_key,
        "epoch": epoch.epoch,
        "members": members_payload,
        "group_name": group.name,
        "group_avatar": group.avatar,
    }


def private_conversation_key(user_a_id: int, user_b_id: int) -> str:
    low = min(user_a_id, user_b_id)
    high = max(user_a_id, user_b_id)
    return f"{low}:{high}"


def get_private_conversation(db: Session, user_a_id: int, user_b_id: int) -> ConversationV2 | None:
    return db.query(ConversationV2).filter(
        ConversationV2.conversation_key == private_conversation_key(user_a_id, user_b_id),
        ConversationV2.conversation_type == "private",
    ).first()


def get_or_create_private_conversation(db: Session, user_a_id: int, user_b_id: int) -> ConversationV2:
    conversation = get_private_conversation(db, user_a_id, user_b_id)
    if conversation is not None:
        return conversation

    low = min(user_a_id, user_b_id)
    high = max(user_a_id, user_b_id)
    conversation = ConversationV2(
        conversation_key=private_conversation_key(user_a_id, user_b_id),
        conversation_type="private",
        pair_user_low_id=low,
        pair_user_high_id=high,
        last_message_at=None,
    )
    db.add(conversation)
    db.flush()
    return conversation


def group_conversation_key(group_id: int) -> str:
    return f"group:{group_id}"


def get_group_conversation(db: Session, group_id: int) -> ConversationV2 | None:
    return db.query(ConversationV2).filter(
        ConversationV2.group_id == group_id,
        ConversationV2.conversation_type == "group",
    ).first()


def get_or_create_group_conversation(db: Session, group_id: int) -> ConversationV2:
    conversation = get_group_conversation(db, group_id)
    if conversation is not None:
        return conversation

    conversation = ConversationV2(
        conversation_key=group_conversation_key(group_id),
        conversation_type="group",
        group_id=group_id,
        last_message_at=None,
    )
    db.add(conversation)
    db.flush()
    return conversation


def get_active_group_sender_key_epoch(db: Session, group_id: int) -> GroupSenderKeyEpoch | None:
    return db.query(GroupSenderKeyEpoch).filter(
        GroupSenderKeyEpoch.group_id == group_id,
        GroupSenderKeyEpoch.status == "active",
    ).order_by(GroupSenderKeyEpoch.epoch.desc(), GroupSenderKeyEpoch.id.desc()).first()


def get_or_create_group_sender_key_epoch(db: Session, group_id: int, rotated_by_user_id: int | None = None) -> GroupSenderKeyEpoch:
    active_epoch = get_active_group_sender_key_epoch(db, group_id)
    if active_epoch is not None:
        return active_epoch

    group_conversation = get_or_create_group_conversation(db, group_id)
    active_epoch = GroupSenderKeyEpoch(
        group_id=group_id,
        epoch=1,
        status="active",
        rotated_by_user_id=rotated_by_user_id,
        distribution_message_id=None,
    )
    db.add(active_epoch)
    db.flush()
    group_conversation.last_message_at = group_conversation.last_message_at
    db.commit()
    db.refresh(active_epoch)
    return active_epoch


def rotate_group_sender_key_epoch(db: Session, group_id: int, rotated_by_user_id: int | None = None) -> GroupSenderKeyEpoch:
    active_epoch = get_active_group_sender_key_epoch(db, group_id)
    next_epoch = 1
    now = naive_utcnow()
    if active_epoch is not None:
        next_epoch = active_epoch.epoch + 1
        active_epoch.status = "retired"
        active_epoch.retired_at = now

    new_epoch = GroupSenderKeyEpoch(
        group_id=group_id,
        epoch=next_epoch,
        status="active",
        rotated_by_user_id=rotated_by_user_id,
        distribution_message_id=None,
        created_at=now,
    )
    db.add(new_epoch)
    get_or_create_group_conversation(db, group_id)
    db.commit()
    db.refresh(new_epoch)
    return new_epoch


def serialize_private_conversation(db: Session, current_user_id: int, conversation: ConversationV2, partner: User) -> dict:
    return {
        "id": conversation.id,
        "conversation_key": conversation.conversation_key,
        "conversation_type": conversation.conversation_type,
        "chat_type": "private",
        "partner_id": partner.id,
        "username": partner.username,
        "avatar": partner.avatar,
        "type": "private",
        "protocol_version": "e2ee_v1",
        "can_chat": crud.can_start_private_chat(db, current_user_id, partner.id),
        "last_message_at": serialize_datetime(conversation.last_message_at),
        **_serialize_last_message_meta(db, conversation.id),
    }


def serialize_group_conversation(db: Session, conversation: ConversationV2, group: Group) -> dict:
    return {
        "id": conversation.id,
        "conversation_key": conversation.conversation_key,
        "conversation_type": conversation.conversation_type,
        "chat_type": "group",
        "group_id": group.id,
        "username": group.name,
        "avatar": group.avatar,
        "type": "group",
        "protocol_version": "e2ee_v1",
        "can_chat": True,
        "last_message_at": serialize_datetime(conversation.last_message_at),
        **_serialize_last_message_meta(db, conversation.id),
    }


def list_private_conversations(db: Session, current_user_id: int) -> list[dict]:
    rows = db.query(ConversationV2).filter(
        ConversationV2.conversation_type == "private",
        or_(
            ConversationV2.pair_user_low_id == current_user_id,
            ConversationV2.pair_user_high_id == current_user_id,
        ),
    ).order_by(
        ConversationV2.last_message_at.is_(None),
        ConversationV2.last_message_at.desc(),
        ConversationV2.id.desc(),
    ).all()

    items = []
    for conversation in rows:
        partner_id = conversation.pair_user_high_id if conversation.pair_user_low_id == current_user_id else conversation.pair_user_low_id
        partner = crud.get_user(db, partner_id)
        if partner is None:
            continue
        items.append(serialize_private_conversation(db, current_user_id, conversation, partner))
    return items


def list_group_conversations(db: Session, current_user_id: int) -> list[dict]:
    groups = db.query(Group).join(
        GroupMember,
        Group.id == GroupMember.group_id,
    ).filter(
        GroupMember.user_id == current_user_id,
    ).order_by(Group.id.asc()).all()
    items = []
    for group in groups:
        conversation = get_or_create_group_conversation(db, group.id)
        items.append(serialize_group_conversation(db, conversation, group))
    if groups:
        db.commit()
    return items


def list_e2ee_conversations(db: Session, current_user_id: int) -> list[dict]:
    return list_private_conversations(db, current_user_id) + list_group_conversations(db, current_user_id)


def init_attachment_blob(
        db: Session,
        *,
        current_user: User,
        current_device: Device,
        mime_type: str,
        ciphertext_size: int,
        ciphertext_sha256: str,
) -> AttachmentBlobV2:
    if ciphertext_size > E2EE_ATTACHMENT_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件过大")
    normalized_mime_type = (mime_type or "application/octet-stream").strip().lower()
    if not _is_allowed_attachment_mime(normalized_mime_type):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的文件类型")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", ciphertext_sha256 or ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="附件哈希无效")

    blob_public_id = secrets.token_hex(16)
    blob = AttachmentBlobV2(
        blob_id=blob_public_id,
        uploader_user_id=current_user.id,
        uploader_device_id=current_device.id,
        message_id=None,
        storage_backend="local",
        storage_path=str(_attachment_storage_path(blob_public_id)),
        mime_type=normalized_mime_type,
        ciphertext_size=ciphertext_size,
        ciphertext_sha256=ciphertext_sha256.lower(),
        status="pending",
        upload_expires_at=_attachment_upload_expiry(),
    )
    db.add(blob)
    db.commit()
    db.refresh(blob)
    return blob


def get_attachment_blob_for_upload(db: Session, blob_id: str, current_user_id: int) -> AttachmentBlobV2:
    blob = db.query(AttachmentBlobV2).filter(AttachmentBlobV2.blob_id == blob_id).first()
    if blob is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")
    if blob.uploader_user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权上传该附件")
    return blob


def store_attachment_blob_bytes(db: Session, *, blob: AttachmentBlobV2, ciphertext: bytes) -> AttachmentBlobV2:
    if blob.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="附件上传状态无效")
    if blob.upload_expires_at and blob.upload_expires_at < naive_utcnow():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="附件上传已过期")
    if len(ciphertext) != blob.ciphertext_size:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="附件大小不匹配")

    storage_path = Path(blob.storage_path)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(ciphertext)
    return blob


def complete_attachment_blob(db: Session, *, blob: AttachmentBlobV2, ciphertext_sha256: str) -> AttachmentBlobV2:
    if blob.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="附件上传状态无效")

    storage_path = Path(blob.storage_path)
    if not storage_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件内容不存在")

    ciphertext = storage_path.read_bytes()
    actual_sha256 = _sha256_hex(ciphertext)
    if actual_sha256 != blob.ciphertext_sha256 or actual_sha256 != ciphertext_sha256.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="附件哈希校验失败")

    blob.status = "complete"
    blob.completed_at = naive_utcnow()
    db.commit()
    db.refresh(blob)
    return blob


def link_attachment_blobs_to_message(
        db: Session,
        *,
        sender: User,
        message: MessageV2,
        blob_ids: list[str],
) -> None:
    if not blob_ids:
        return

    blobs = db.query(AttachmentBlobV2).filter(AttachmentBlobV2.blob_id.in_(blob_ids)).all()
    blob_map = {blob.blob_id: blob for blob in blobs}
    if len(blob_map) != len(set(blob_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    for blob_id in blob_ids:
        blob = blob_map[blob_id]
        if blob.uploader_user_id != sender.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权绑定该附件")
        if blob.status != "complete":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="附件尚未完成上传")
        if blob.message_id is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="附件已绑定消息")
        blob.message_id = message.id


def get_attachment_blob_for_download(db: Session, *, blob_id: str, current_user_id: int) -> AttachmentBlobV2:
    blob = db.query(AttachmentBlobV2).filter(AttachmentBlobV2.blob_id == blob_id).first()
    if blob is None or blob.status != "complete":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")
    if not Path(blob.storage_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    if blob.uploader_user_id == current_user_id:
        return blob

    if blob.message_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该附件")

    message = db.query(MessageV2).filter(MessageV2.id == blob.message_id).first()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")
    if message.is_recalled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    conversation = db.query(ConversationV2).filter(ConversationV2.id == message.conversation_id).first()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    if conversation.conversation_type == "private":
        allowed_user_ids = {conversation.pair_user_low_id, conversation.pair_user_high_id}
        if current_user_id not in allowed_user_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该附件")
        return blob

    if conversation.conversation_type == "group":
        member_ids = set(crud.get_group_members(db, conversation.group_id))
        if current_user_id not in member_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该附件")
        return blob

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该附件")


def _resolve_device_row(db: Session, recipient_user_id: int, recipient_device_public_id: str) -> Device:
    device = db.query(Device).filter(
        Device.user_id == recipient_user_id,
        Device.device_id == recipient_device_public_id,
        Device.is_active.is_(True),
        Device.revoked_at.is_(None),
    ).first()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标设备不存在")
    return device


def _serialize_envelope_value(envelope) -> str:
    if isinstance(envelope, str):
        return envelope
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))


def _sender_device_public_id(sender_device: Device | None) -> str | None:
    return sender_device.device_id if sender_device else None


def _build_message_event(
        current_user_id: int,
        conversation: ConversationV2,
        message: MessageV2,
        sender: User,
        sender_device: Device | None,
        payload_rows: list[tuple[MessagePayload, Device]],
) -> dict:
    partner_id = conversation.pair_user_high_id if conversation.pair_user_low_id == current_user_id else conversation.pair_user_low_id
    return {
        "type": "message.new",
        "chat_type": "private",
        "conversation_id": conversation.id,
        "conversation_key": conversation.conversation_key,
        "partner_id": partner_id,
        "message": {
            "id": message.id,
            "sender_user_id": message.sender_user_id,
            "sender_device_id": _sender_device_public_id(sender_device),
            "client_message_id": message.client_message_id,
            "message_type": message.message_type,
            "protocol_version": message.protocol_version,
            "created_at": serialize_datetime(message.created_at),
            "username": sender.username,
            "avatar": sender.avatar,
        },
        "payloads": [
            {
                "recipient_device_id": device.device_id,
                "envelope_type": payload.envelope_type,
                "envelope": payload.envelope,
            }
            for payload, device in payload_rows
        ],
    }


def _build_group_message_event(
        current_user_id: int,
        conversation: ConversationV2,
        group: Group,
        message: MessageV2,
        sender: User,
        sender_device: Device | None,
        payload_rows: list[tuple[MessagePayload, Device]],
) -> dict:
    return {
        "type": "message.new",
        "chat_type": "group",
        "conversation_id": conversation.id,
        "conversation_key": conversation.conversation_key,
        "group_id": group.id,
        "group_name": group.name,
        "group_avatar": group.avatar,
        "message": {
            "id": message.id,
            "sender_user_id": message.sender_user_id,
            "sender_device_id": _sender_device_public_id(sender_device),
            "client_message_id": message.client_message_id,
            "message_type": message.message_type,
            "protocol_version": message.protocol_version,
            "created_at": serialize_datetime(message.created_at),
            "username": sender.username,
            "avatar": sender.avatar,
        },
        "payloads": [
            {
                "recipient_device_id": device.device_id,
                "envelope_type": payload.envelope_type,
                "envelope": payload.envelope,
            }
            for payload, device in payload_rows
        ],
    }


def _build_message_recalled_event(
        current_user_id: int,
        conversation: ConversationV2,
        message: MessageV2,
        sender: User,
        *,
        is_latest_message: bool,
        group: Group | None = None,
) -> dict:
    payload = {
        "type": "message.recalled",
        "chat_type": conversation.conversation_type,
        "conversation_id": conversation.id,
        "message": {
            "id": message.id,
            "sender_user_id": message.sender_user_id,
            "client_message_id": message.client_message_id,
            "message_type": message.message_type,
            "protocol_version": message.protocol_version,
            "created_at": serialize_datetime(message.created_at),
            "username": sender.username,
            "avatar": sender.avatar,
            "is_recalled": True,
            "recalled_at": serialize_datetime(message.recalled_at),
            "recalled_by_user_id": message.recalled_by_user_id,
        },
        "is_latest_message": is_latest_message,
    }

    if conversation.conversation_type == "private":
        partner_id = conversation.pair_user_high_id if conversation.pair_user_low_id == current_user_id else conversation.pair_user_low_id
        payload["partner_id"] = partner_id
        return payload

    if group is not None:
        payload["group_id"] = group.id
        payload["group_name"] = group.name
        payload["group_avatar"] = group.avatar
    return payload


def _append_message_recall_fields(item: dict, message: MessageV2) -> dict:
    item["is_recalled"] = bool(message.is_recalled)
    item["recalled_at"] = serialize_datetime(message.recalled_at)
    item["recalled_by_user_id"] = message.recalled_by_user_id
    return item


def _delivery_status_rank(status_value: str) -> int:
    return {
        "failed": -1,
        "pending": 0,
        "delivered": 1,
        "read": 2,
    }.get(status_value, 0)


def _delivery_sort_datetime(delivery: MessageDelivery) -> datetime:
    return delivery.read_at or delivery.delivered_at or delivery.updated_at or datetime.min


def _build_receipt_summary_map(db: Session, messages: list[MessageV2]) -> dict[int, dict]:
    if not messages:
        return {}

    message_ids = [message.id for message in messages]
    sender_user_by_message = {message.id: message.sender_user_id for message in messages}
    rows = db.query(MessageDelivery, User).join(
        User,
        User.id == MessageDelivery.recipient_user_id,
    ).filter(
        MessageDelivery.message_id.in_(message_ids),
    ).all()

    summary_by_message: dict[int, dict[int, dict]] = {}
    for delivery, user in rows:
        sender_user_id = sender_user_by_message.get(delivery.message_id)
        if sender_user_id is not None and user.id == sender_user_id:
            continue

        per_user_map = summary_by_message.setdefault(delivery.message_id, {})
        current_entry = per_user_map.get(user.id)
        next_rank = _delivery_status_rank(delivery.status)
        next_dt = _delivery_sort_datetime(delivery)
        if current_entry is not None:
            current_rank = _delivery_status_rank(current_entry["status"])
            if current_rank > next_rank:
                continue
            if current_rank == next_rank and current_entry["sort_at"] >= next_dt:
                continue

        per_user_map[user.id] = {
            "user_id": user.id,
            "username": user.username,
            "avatar": user.avatar,
            "status": delivery.status,
            "read_at": serialize_datetime(delivery.read_at),
            "delivered_at": serialize_datetime(delivery.delivered_at),
            "sort_at": next_dt,
        }

    receipt_summary_map: dict[int, dict] = {}
    for message in messages:
        per_user_map = summary_by_message.get(message.id, {})
        delivered_users = []
        read_users = []
        for entry in per_user_map.values():
            if _delivery_status_rank(entry["status"]) >= 1:
                delivered_users.append(entry)
            if entry["status"] == "read":
                read_users.append(entry)

        delivered_users.sort(key=lambda item: item["sort_at"])
        read_users.sort(key=lambda item: item["sort_at"])

        receipt_summary_map[message.id] = {
            "status": "read" if read_users else ("delivered" if delivered_users else "sent"),
            "delivered_user_count": len(delivered_users),
            "read_user_count": len(read_users),
            "read_by": [
                {
                    "user_id": entry["user_id"],
                    "username": entry["username"],
                    "avatar": entry["avatar"],
                    "read_at": entry["read_at"],
                }
                for entry in read_users
            ],
        }

    return receipt_summary_map


def create_private_message(
        db: Session,
        *,
        sender: User,
        sender_device: Device | None,
        target_user_id: int,
        client_message_id: str | None,
        message_type: str,
        packets: list[dict],
        attachment_blob_ids: list[str] | None = None,
) -> dict:
    if target_user_id == sender.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能向自己发送私聊消息")
    if not crud.can_start_private_chat(db, sender.id, target_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前无权发送私聊消息")
    if sender_device is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前会话尚未绑定设备")
    if not packets:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E2EE 消息缺少设备 envelope")

    existing_message = None
    if client_message_id:
        existing_message = db.query(MessageV2).filter(
            MessageV2.sender_device_id == sender_device.id,
            MessageV2.client_message_id == client_message_id,
        ).first()
    if existing_message is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="消息已发送")

    conversation = get_or_create_private_conversation(db, sender.id, target_user_id)
    now = naive_utcnow()
    message = MessageV2(
        conversation_id=conversation.id,
        sender_user_id=sender.id,
        sender_device_id=sender_device.id,
        client_message_id=client_message_id,
        protocol_version="e2ee_v1",
        message_type=message_type,
        has_attachments=bool(attachment_blob_ids),
        created_at=now,
    )
    db.add(message)
    db.flush()

    payload_rows_by_user: dict[int, list[tuple[MessagePayload, Device]]] = {}
    for packet in packets:
        recipient_user_id = int(packet["recipient_user_id"])
        recipient_device_public_id = packet["recipient_device_id"]
        envelope_type = packet.get("envelope_type", "signal")
        envelope = _serialize_envelope_value(packet["envelope"])
        if recipient_user_id not in {target_user_id, sender.id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="E2EE 消息存在非法接收设备")
        device = _resolve_device_row(db, recipient_user_id, recipient_device_public_id)

        payload_row = MessagePayload(
            message_id=message.id,
            recipient_user_id=recipient_user_id,
            recipient_device_id=device.id,
            envelope_type=envelope_type,
            protocol_version="e2ee_v1",
            envelope=envelope,
            created_at=now,
        )
        db.add(payload_row)

        initial_status = "read" if recipient_user_id == sender.id and device.id == sender_device.id else "pending"
        delivery_row = MessageDelivery(
            message_id=message.id,
            recipient_user_id=recipient_user_id,
            recipient_device_id=device.id,
            status=initial_status,
            delivered_at=now if initial_status == "read" else None,
            read_at=now if initial_status == "read" else None,
            updated_at=now,
        )
        db.add(delivery_row)
        payload_rows_by_user.setdefault(recipient_user_id, []).append((payload_row, device))

    link_attachment_blobs_to_message(db, sender=sender, message=message, blob_ids=attachment_blob_ids or [])
    conversation.last_message_at = now
    db.commit()
    db.refresh(message)

    sender_row = crud.get_user(db, sender.id) or sender
    sender_device_row = _resolve_device_row(db, sender.id, sender_device.device_id)

    recipient_events = {
        user_id: _build_message_event(user_id, conversation, message, sender_row, sender_device_row, rows)
        for user_id, rows in payload_rows_by_user.items()
    }
    return {
        "conversation": conversation,
        "message": message,
        "events": recipient_events,
    }


def create_group_message(
        db: Session,
        *,
        sender: User,
        sender_device: Device | None,
        group_id: int,
        group_epoch: int,
        client_message_id: str | None,
        message_type: str,
        packets: list[dict],
        attachment_blob_ids: list[str] | None = None,
) -> dict:
    if sender_device is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前会话尚未绑定设备")
    if not packets:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E2EE 消息缺少设备 envelope")

    group = crud.get_group(db, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="群组不存在")
    member_ids = set(crud.get_group_members(db, group_id))
    if sender.id not in member_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权向该群组发送消息")

    active_epoch = get_or_create_group_sender_key_epoch(db, group_id, sender.id)
    if group_epoch != active_epoch.epoch:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="群组 sender key epoch 已过期")

    existing_message = None
    if client_message_id:
        existing_message = db.query(MessageV2).filter(
            MessageV2.sender_device_id == sender_device.id,
            MessageV2.client_message_id == client_message_id,
        ).first()
    if existing_message is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="消息已发送")

    conversation = get_or_create_group_conversation(db, group_id)
    now = naive_utcnow()
    message = MessageV2(
        conversation_id=conversation.id,
        sender_user_id=sender.id,
        sender_device_id=sender_device.id,
        client_message_id=client_message_id,
        protocol_version="e2ee_v1",
        message_type=message_type,
        has_attachments=bool(attachment_blob_ids),
        created_at=now,
    )
    db.add(message)
    db.flush()

    payload_rows_by_user: dict[int, list[tuple[MessagePayload, Device]]] = {}
    allowed_recipient_user_ids = member_ids | {sender.id}
    for packet in packets:
        recipient_user_id = int(packet["recipient_user_id"])
        recipient_device_public_id = packet["recipient_device_id"]
        envelope_type = packet.get("envelope_type", "group_sender_key")
        envelope = _serialize_envelope_value(packet["envelope"])
        if recipient_user_id not in allowed_recipient_user_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="E2EE 消息存在非法接收设备")
        device = _resolve_device_row(db, recipient_user_id, recipient_device_public_id)

        payload_row = MessagePayload(
            message_id=message.id,
            recipient_user_id=recipient_user_id,
            recipient_device_id=device.id,
            envelope_type=envelope_type,
            protocol_version="e2ee_v1",
            envelope=envelope,
            created_at=now,
        )
        db.add(payload_row)

        initial_status = "read" if recipient_user_id == sender.id and device.id == sender_device.id else "pending"
        delivery_row = MessageDelivery(
            message_id=message.id,
            recipient_user_id=recipient_user_id,
            recipient_device_id=device.id,
            status=initial_status,
            delivered_at=now if initial_status == "read" else None,
            read_at=now if initial_status == "read" else None,
            updated_at=now,
        )
        db.add(delivery_row)
        payload_rows_by_user.setdefault(recipient_user_id, []).append((payload_row, device))

    link_attachment_blobs_to_message(db, sender=sender, message=message, blob_ids=attachment_blob_ids or [])
    if message_type == "sender_key_distribution" and active_epoch.distribution_message_id is None:
        active_epoch.distribution_message_id = message.id
    conversation.last_message_at = now
    db.commit()
    db.refresh(message)

    sender_row = crud.get_user(db, sender.id) or sender
    sender_device_row = _resolve_device_row(db, sender.id, sender_device.device_id)
    recipient_events = {
        user_id: _build_group_message_event(user_id, conversation, group, message, sender_row, sender_device_row, rows)
        for user_id, rows in payload_rows_by_user.items()
    }
    return {
        "conversation": conversation,
        "message": message,
        "events": recipient_events,
    }


def recall_message(
        db: Session,
        *,
        current_user_id: int,
        message_id: int,
) -> dict:
    message = db.query(MessageV2).filter(MessageV2.id == message_id).first()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")
    if message.sender_user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无法撤回他人的消息")
    if message.message_type == "sender_key_distribution":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前消息不支持撤回")

    conversation = db.query(ConversationV2).filter(ConversationV2.id == message.conversation_id).first()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="E2EE 会话不存在")

    sender = crud.get_user(db, current_user_id)
    if sender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标用户不存在")

    latest_message = db.query(MessageV2).filter(
        MessageV2.conversation_id == conversation.id,
    ).order_by(
        MessageV2.created_at.desc(),
        MessageV2.id.desc(),
    ).first()
    is_latest_message = latest_message is not None and latest_message.id == message.id

    if not message.is_recalled:
        message.is_recalled = True
        message.recalled_at = naive_utcnow()
        message.recalled_by_user_id = current_user_id
        db.commit()
        db.refresh(message)

    recipient_user_ids = {
        recipient_user_id
        for recipient_user_id, in db.query(MessagePayload.recipient_user_id).filter(
            MessagePayload.message_id == message.id,
        ).distinct().all()
    }

    group = crud.get_group(db, conversation.group_id) if conversation.conversation_type == "group" else None
    events = {
        recipient_user_id: _build_message_recalled_event(
            recipient_user_id,
            conversation,
            message,
            sender,
            is_latest_message=is_latest_message,
            group=group,
        )
        for recipient_user_id in recipient_user_ids
    }

    return {
        "conversation": conversation,
        "message": message,
        "events": events,
        "is_latest_message": is_latest_message,
    }


def list_conversation_messages_for_device(
        db: Session,
        *,
        current_user_id: int,
        device: Device,
        conversation_id: int,
        limit: int = 200,
) -> list[dict]:
    conversation = db.query(ConversationV2).filter(
        ConversationV2.id == conversation_id,
        or_(
            (ConversationV2.conversation_type == "private") & or_(
                ConversationV2.pair_user_low_id == current_user_id,
                ConversationV2.pair_user_high_id == current_user_id,
            ),
            (ConversationV2.conversation_type == "group") & (ConversationV2.group_id.in_(
                db.query(GroupMember.group_id).filter(GroupMember.user_id == current_user_id)
            )),
        ),
    ).first()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="E2EE 会话不存在")

    rows = db.query(MessageV2, MessagePayload, MessageDelivery, User, Device).join(
        MessagePayload,
        MessagePayload.message_id == MessageV2.id,
    ).join(
        MessageDelivery,
        (MessageDelivery.message_id == MessageV2.id) & (MessageDelivery.recipient_device_id == MessagePayload.recipient_device_id),
    ).join(
        User,
        User.id == MessageV2.sender_user_id,
    ).outerjoin(
        Device,
        Device.id == MessageV2.sender_device_id,
    ).filter(
        MessageV2.conversation_id == conversation.id,
        MessagePayload.recipient_device_id == device.id,
    ).order_by(MessageV2.created_at.asc(), MessageV2.id.asc()).limit(limit).all()

    receipt_summary_map = _build_receipt_summary_map(db, [message for message, _, _, _, _ in rows])
    items = []
    for message, payload, delivery, sender, sender_device in rows:
        item = {
            "conversation_id": conversation.id,
            "chat_type": conversation.conversation_type,
            "message_id": message.id,
            "sender_user_id": message.sender_user_id,
            "sender_device_id": sender_device.device_id if sender_device else None,
            "client_message_id": message.client_message_id,
            "message_type": message.message_type,
            "protocol_version": message.protocol_version,
            "created_at": serialize_datetime(message.created_at),
            "username": sender.username,
            "avatar": sender.avatar,
            "delivery_status": delivery.status,
            "receipt_summary": receipt_summary_map.get(message.id, {"status": "sent", "delivered_user_count": 0, "read_user_count": 0, "read_by": []}),
            "envelope_type": payload.envelope_type,
            "envelope": payload.envelope,
        }
        _append_message_recall_fields(item, message)
        if conversation.conversation_type == "private":
            item["partner_id"] = conversation.pair_user_high_id if conversation.pair_user_low_id == current_user_id else conversation.pair_user_low_id
        else:
            group = crud.get_group(db, conversation.group_id)
            item["group_id"] = conversation.group_id
            item["group_name"] = group.name if group else None
            item["group_avatar"] = group.avatar if group else None
        items.append(item)
    return items


def list_inbox_for_device(
        db: Session,
        *,
        current_user_id: int,
        device: Device,
        limit: int = 200,
) -> list[dict]:
    rows = db.query(MessageV2, MessagePayload, MessageDelivery, User, Device, ConversationV2).join(
        MessagePayload,
        MessagePayload.message_id == MessageV2.id,
    ).join(
        MessageDelivery,
        (MessageDelivery.message_id == MessageV2.id) & (MessageDelivery.recipient_device_id == MessagePayload.recipient_device_id),
    ).join(
        User,
        User.id == MessageV2.sender_user_id,
    ).outerjoin(
        Device,
        Device.id == MessageV2.sender_device_id,
    ).join(
        ConversationV2,
        ConversationV2.id == MessageV2.conversation_id,
    ).filter(
        MessagePayload.recipient_device_id == device.id,
        MessageDelivery.recipient_user_id == current_user_id,
        MessageDelivery.status == "pending",
    ).order_by(MessageV2.created_at.asc(), MessageV2.id.asc()).limit(limit).all()

    items = []
    for message, payload, delivery, sender, sender_device, conversation in rows:
        partner_id = conversation.pair_user_low_id if conversation.pair_user_high_id == current_user_id else conversation.pair_user_high_id
        item = {
            "conversation_id": conversation.id,
            "conversation_key": conversation.conversation_key,
            "chat_type": conversation.conversation_type,
            "partner_id": partner_id if conversation.conversation_type == "private" else None,
            "message_id": message.id,
            "sender_user_id": message.sender_user_id,
            "sender_device_id": sender_device.device_id if sender_device else None,
            "client_message_id": message.client_message_id,
            "message_type": message.message_type,
            "protocol_version": message.protocol_version,
            "created_at": serialize_datetime(message.created_at),
            "username": sender.username,
            "avatar": sender.avatar,
            "delivery_status": delivery.status,
            "envelope_type": payload.envelope_type,
            "envelope": payload.envelope,
        }
        _append_message_recall_fields(item, message)
        if conversation.conversation_type == "private":
            item["partner_id"] = conversation.pair_user_high_id if conversation.pair_user_low_id == current_user_id else conversation.pair_user_low_id
        else:
            group = crud.get_group(db, conversation.group_id)
            item["group_id"] = conversation.group_id
            item["group_name"] = group.name if group else None
            item["group_avatar"] = group.avatar if group else None
        items.append(item)
    return items


def ack_message_for_device(
        db: Session,
        *,
        current_user_id: int,
        device: Device,
        message_id: int,
        status_value: str,
) -> dict:
    if status_value not in {"delivered", "read"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的消息确认状态")

    delivery = db.query(MessageDelivery).filter(
        MessageDelivery.message_id == message_id,
        MessageDelivery.recipient_user_id == current_user_id,
        MessageDelivery.recipient_device_id == device.id,
    ).first()
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息投递状态不存在")

    now = naive_utcnow()
    if status_value == "delivered":
        if delivery.status == "pending":
            delivery.status = "delivered"
            delivery.delivered_at = now
    else:
        delivery.status = "read"
        if delivery.delivered_at is None:
            delivery.delivered_at = now
        delivery.read_at = now
    delivery.updated_at = now
    db.commit()

    message = db.query(MessageV2).filter(MessageV2.id == delivery.message_id).first()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")

    receipt_summary = _build_receipt_summary_map(db, [message]).get(message.id, {
        "status": delivery.status,
        "delivered_user_count": 0,
        "read_user_count": 0,
        "read_by": [],
    })

    return {
        "message_id": message.id,
        "status": receipt_summary["status"],
        "receipt_summary": receipt_summary,
        "sender_user_id": message.sender_user_id,
        "conversation_id": message.conversation_id,
        "recipient_device_id": device.device_id,
    }
