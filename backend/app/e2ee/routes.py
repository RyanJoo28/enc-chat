import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from ..chat.manager import manager as chat_manager
from ..database import crud, get_db
from ..database.models import Device, GroupMember
from ..user.auth_service import bind_session_to_device, build_auth_response_payload, mark_session_used
from ..user.dependencies import AuthContext, get_auth_context
from ..utils.limiter import get_auth_or_remote_address, limiter
from .schemas import (
    AttachmentCompleteRequest,
    AttachmentInitRequest,
    DeviceBootstrapRequest,
    DevicePrekeyRefreshRequest,
)
from .service import (
    complete_attachment_blob,
    claim_prekey_bundle,
    get_group_member_devices,
    get_active_device_for_user,
    get_attachment_blob_for_download,
    get_attachment_blob_for_upload,
    get_device_for_user,
    init_attachment_blob,
    list_active_devices_for_user,
    list_devices_for_user,
    list_conversation_messages_for_device,
    list_e2ee_conversations,
    list_inbox_for_device,
    naive_utcnow,
    recall_message,
    revoke_device_for_user,
    rotate_group_sender_key_epoch,
    serialize_device_summary,
    serialize_owned_device_summary,
    store_attachment_blob_bytes,
    ws_ticket_store,
)


router = APIRouter()


def _require_session(auth_context: AuthContext):
    if auth_context.auth_session is None:
        raise HTTPException(status_code=401, detail="当前访问令牌未绑定刷新会话")
    return auth_context.auth_session


def _require_device(db: Session, user_id: int, device_public_id: str) -> Device:
    device = get_active_device_for_user(db, user_id, device_public_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


def _active_device_count(db: Session, user_id: int) -> int:
    return len(list_active_devices_for_user(db, user_id))


def _related_user_ids_for_device_updates(db: Session, user_id: int) -> set[int]:
    related_user_ids = set(crud.get_friend_ids(db, user_id))
    joined_group_ids = [group_id for group_id, in db.query(GroupMember.group_id).filter(GroupMember.user_id == user_id).all()]
    if joined_group_ids:
        related_user_ids.update(
            member_id
            for member_id, in db.query(GroupMember.user_id).filter(GroupMember.group_id.in_(joined_group_ids)).all()
            if member_id != user_id
        )
    related_user_ids.discard(user_id)
    return related_user_ids


async def _broadcast_device_added(
        db: Session,
        *,
        user_id: int,
        payload: dict,
) -> None:
    recipient_ids = {user_id}
    recipient_ids.update(_related_user_ids_for_device_updates(db, user_id))
    await chat_manager.broadcast_device_added(recipient_ids, payload)


async def _broadcast_device_revoked(
        db: Session,
        *,
        user_id: int,
        payload: dict,
) -> None:
    recipient_ids = {user_id}
    recipient_ids.update(_related_user_ids_for_device_updates(db, user_id))
    await chat_manager.broadcast_device_revoked(recipient_ids, payload)


@router.post("/devices/bootstrap")
@limiter.limit("30/minute", key_func=get_auth_or_remote_address)
async def bootstrap_device(
        request: Request,
        payload: DeviceBootstrapRequest,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """为当前会话注册或重绑定浏览器设备。"""
    auth_session = _require_session(auth_context)
    existing_device = get_device_for_user(db, auth_context.user.id, payload.device_id)
    now = naive_utcnow()
    is_new_device = existing_device is None
    if existing_device and existing_device.revoked_at is not None:
        raise HTTPException(status_code=409, detail="设备已被撤销")

    if existing_device is None:
        device = Device(
            device_id=payload.device_id,
            user_id=auth_context.user.id,
            device_name=payload.device_name,
            platform=payload.platform,
            identity_key_public=payload.identity_key_public,
            signing_key_public=payload.signing_key_public,
            registration_id=payload.registration_id,
            is_active=True,
            last_seen_at=now,
        )
        db.add(device)
        db.flush()
    else:
        device = existing_device
        device.device_name = payload.device_name
        device.platform = payload.platform
        device.identity_key_public = payload.identity_key_public
        device.signing_key_public = payload.signing_key_public
        device.registration_id = payload.registration_id
        device.is_active = True
        device.revoked_at = None
        device.last_seen_at = now

    from .service import replace_device_keys

    replace_device_keys(
        db,
        device=device,
        signed_prekey=payload.signed_prekey,
        one_time_prekeys=payload.one_time_prekeys,
    )

    auth_context.user.e2ee_enabled = True
    bind_session_to_device(db, auth_session, device)
    mark_session_used(db, auth_session, ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
    db.refresh(device)
    db.refresh(auth_context.user)
    active_device_count = _active_device_count(db, auth_context.user.id)

    if is_new_device:
        await _broadcast_device_added(
            db,
            user_id=auth_context.user.id,
            payload={
                "user_id": auth_context.user.id,
                "device_id": device.device_id,
                "device_name": device.device_name,
                "platform": device.platform,
                "active_device_count": active_device_count,
            },
        )

    return {
        "device": serialize_device_summary(db, device),
        "active_device_count": active_device_count,
        **build_auth_response_payload(db, auth_context.user, auth_session),
    }


@router.get("/devices/me")
async def get_my_device(
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """返回当前 refresh session 绑定的设备。"""
    auth_session = _require_session(auth_context)
    if auth_session.device_id is None:
        return {"device": None, "active_device_count": 0}

    device = get_active_device_for_user(db, auth_context.user.id, auth_context.device.device_id) if auth_context.device else None
    if device is None:
        return {"device": None, "active_device_count": 0}

    return {
        "device": serialize_device_summary(db, device),
        "active_device_count": _active_device_count(db, auth_context.user.id),
    }


@router.get("/devices")
async def list_my_devices(
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """返回当前用户的全部设备清单（含已撤销设备）。"""
    _require_session(auth_context)
    current_device_public_id = auth_context.device.device_id if auth_context.device else None
    devices = list_devices_for_user(db, auth_context.user.id)
    return {
        "devices": [
            serialize_owned_device_summary(db, device, current_device_public_id=current_device_public_id)
            for device in devices
        ],
        "active_device_count": _active_device_count(db, auth_context.user.id),
    }


@router.post("/devices/{device_id}/prekeys/refresh")
@limiter.limit("30/minute", key_func=get_auth_or_remote_address)
async def refresh_device_prekeys(
        device_id: str,
        request: Request,
        payload: DevicePrekeyRefreshRequest,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """更新指定设备的 signed prekey 和 one-time prekeys。"""
    _require_session(auth_context)
    if auth_context.device is None or auth_context.device.device_id != device_id:
        raise HTTPException(status_code=403, detail="无权更新该设备的 prekeys")

    device = _require_device(db, auth_context.user.id, device_id)

    from .service import append_device_one_time_prekeys, replace_active_signed_prekey

    if payload.signed_prekey is not None:
        replace_active_signed_prekey(db, device=device, signed_prekey=payload.signed_prekey)

    added_count = append_device_one_time_prekeys(db, device=device, one_time_prekeys=payload.one_time_prekeys)
    device.last_seen_at = naive_utcnow()
    db.commit()
    db.refresh(device)

    if auth_context.auth_session:
        mark_session_used(db, auth_context.auth_session, ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))

    return {
        "device": serialize_device_summary(db, device),
        "added_one_time_prekeys": added_count,
    }


@router.post("/devices/{device_id}/revoke")
async def revoke_device(
        device_id: str,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """撤销当前用户的某台设备，并使其 refresh session 与 WebSocket 失效。"""
    _require_session(auth_context)
    if auth_context.device is not None and auth_context.device.device_id == device_id:
        raise HTTPException(status_code=400, detail="不能撤销当前设备")

    result = revoke_device_for_user(db, user_id=auth_context.user.id, device_public_id=device_id)
    device = result["device"]
    event_payload = {
        "user_id": auth_context.user.id,
        "device_id": device.device_id,
        "active_device_count": result["active_device_count"],
    }

    rotated_group_ids = []
    if result["did_revoke"]:
        await _broadcast_device_revoked(
            db,
            user_id=auth_context.user.id,
            payload=event_payload,
        )
        await chat_manager.disconnect_device(auth_context.user.id, device_id, close_code=4001, reason="device_revoked")

        for group_id in result["group_ids"]:
            member_ids = crud.get_group_members(db, group_id)
            if not member_ids:
                continue
            epoch = rotate_group_sender_key_epoch(db, group_id, auth_context.user.id)
            rotated_group_ids.append(group_id)
            await chat_manager.broadcast_group_epoch_changed(member_ids, group_id, epoch.epoch)

    return {
        "device": serialize_owned_device_summary(
            db,
            device,
            current_device_public_id=auth_context.device.device_id if auth_context.device else None,
        ),
        "did_revoke": result["did_revoke"],
        "active_device_count": result["active_device_count"],
        "revoked_session_count": result["revoked_session_count"],
        "rotated_group_ids": rotated_group_ids,
    }


@router.get("/users/{user_id}/prekey-bundle")
async def get_prekey_bundle(
        user_id: int,
        peek: bool = Query(False),
        device_ids: list[str] | None = Query(None),
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
): 
    """为目标用户领取每台设备的 prekey bundle。"""
    _require_session(auth_context)
    if user_id != auth_context.user.id and not crud.can_start_private_chat(db, auth_context.user.id, user_id):
        raise HTTPException(status_code=403, detail="当前无权获取该用户的 prekey bundle")

    return claim_prekey_bundle(
        db,
        user_id,
        consume_one_time_prekeys=not peek,
        device_public_ids=set(device_ids or []),
    )


@router.get("/conversations")
async def get_private_e2ee_conversations(
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """返回当前用户的 E2EE 会话列表。"""
    _require_session(auth_context)
    return list_e2ee_conversations(db, auth_context.user.id)


@router.get("/groups/{group_id}/member-devices")
async def get_group_member_device_bundles(
        group_id: int,
        consume: bool = Query(False),
        user_id: int | None = Query(None),
        device_ids: list[str] | None = Query(None),
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """返回群组成员设备及当前 sender key epoch。"""
    _require_session(auth_context)
    return get_group_member_devices(
        db,
        group_id=group_id,
        current_user_id=auth_context.user.id,
        consume_one_time_prekeys=consume,
        target_user_id=user_id,
        device_public_ids=set(device_ids or []),
    )


@router.post("/groups/{group_id}/request-sender-keys")
async def request_group_sender_keys(
        group_id: int,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """请求其他群成员将自己的 sender key 发送给自己（用于新加入的成员主动获取密钥）。"""
    _require_session(auth_context)
    from ..chat.manager import manager as chat_manager
    from ..database import crud as chat_crud

    member_ids = chat_crud.get_group_members(db, group_id)
    if auth_context.user.id not in member_ids:
        raise HTTPException(status_code=403, detail="不是群组成员")

    payload = json.dumps({
        "type": "sender_key_request_response",
        "group_id": group_id,
        "requester_user_id": auth_context.user.id,
    })

    for member_id in member_ids:
        if member_id == auth_context.user.id:
            continue
        await chat_manager.send_to_user(member_id, payload)

    return {"message": "已通知各成员发送密钥"}


@router.get("/inbox")
async def get_device_inbox(
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """返回当前设备待处理的密文 envelope。"""
    _require_session(auth_context)
    if auth_context.device is None:
        raise HTTPException(status_code=400, detail="当前会话尚未绑定设备")
    return list_inbox_for_device(db, current_user_id=auth_context.user.id, device=auth_context.device)


@router.get("/conversations/{conversation_id}/messages")
async def get_private_e2ee_history(
        conversation_id: int,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """返回当前设备可见的私聊 E2EE 消息历史。"""
    _require_session(auth_context)
    if auth_context.device is None:
        raise HTTPException(status_code=400, detail="当前会话尚未绑定设备")
    return list_conversation_messages_for_device(
        db,
        current_user_id=auth_context.user.id,
        device=auth_context.device,
        conversation_id=conversation_id,
    )


@router.post("/messages/{message_id}/recall")
async def recall_e2ee_message(
        message_id: int,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """撤回当前用户发送的私聊或群聊消息。"""
    _require_session(auth_context)
    result = recall_message(db, current_user_id=auth_context.user.id, message_id=message_id)
    for target_user_id, event_payload in result["events"].items():
        await chat_manager.send_to_user(target_user_id, json.dumps(event_payload, ensure_ascii=False))

    caller_payload = result["events"].get(auth_context.user.id)
    if caller_payload is not None:
        return caller_payload

    return {
        "type": "message.recalled",
        "message": {
            "id": result["message"].id,
            "is_recalled": True,
            "recalled_at": result["message"].recalled_at.isoformat() if result["message"].recalled_at else None,
            "recalled_by_user_id": result["message"].recalled_by_user_id,
        },
        "is_latest_message": result["is_latest_message"],
    }


@router.post("/attachments/init")
async def init_e2ee_attachment(
        payload: AttachmentInitRequest,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """初始化新的加密附件上传。"""
    _require_session(auth_context)
    if auth_context.device is None:
        raise HTTPException(status_code=400, detail="当前会话尚未绑定设备")

    blob = init_attachment_blob(
        db,
        current_user=auth_context.user,
        current_device=auth_context.device,
        mime_type=payload.mime_type,
        ciphertext_size=payload.ciphertext_size,
        ciphertext_sha256=payload.ciphertext_sha256,
    )
    return {
        "blob_id": blob.blob_id,
        "status": blob.status,
        "ciphertext_size": blob.ciphertext_size,
        "mime_type": blob.mime_type,
        "upload_expires_at": blob.upload_expires_at.isoformat() if blob.upload_expires_at else None,
    }


@router.put("/attachments/{blob_id}")
async def upload_e2ee_attachment(
        blob_id: str,
        request: Request,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """上传附件密文 blob。"""
    _require_session(auth_context)
    blob = get_attachment_blob_for_upload(db, blob_id, auth_context.user.id)
    ciphertext = await request.body()
    store_attachment_blob_bytes(db, blob=blob, ciphertext=ciphertext)
    return {"blob_id": blob.blob_id, "uploaded": True}


@router.post("/attachments/{blob_id}/complete")
async def complete_e2ee_attachment(
        blob_id: str,
        payload: AttachmentCompleteRequest,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """完成附件上传并校验密文哈希。"""
    _require_session(auth_context)
    blob = get_attachment_blob_for_upload(db, blob_id, auth_context.user.id)
    blob = complete_attachment_blob(db, blob=blob, ciphertext_sha256=payload.ciphertext_sha256)
    return {
        "blob_id": blob.blob_id,
        "status": blob.status,
        "ciphertext_size": blob.ciphertext_size,
        "mime_type": blob.mime_type,
    }


@router.get("/attachments/{blob_id}")
async def download_e2ee_attachment(
        blob_id: str,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """下载附件密文 blob，由客户端本地解密。"""
    _require_session(auth_context)
    blob = get_attachment_blob_for_download(db, blob_id=blob_id, current_user_id=auth_context.user.id)
    ciphertext = Path(blob.storage_path).read_bytes()
    return Response(content=ciphertext, media_type="application/octet-stream")


@router.post("/ws-ticket")
@limiter.limit("60/minute", key_func=get_auth_or_remote_address)
async def create_ws_ticket(
        request: Request,
        auth_context: AuthContext = Depends(get_auth_context)
):
    """为当前设备生成一次性 WebSocket ticket。"""
    auth_session = _require_session(auth_context)
    if auth_context.device is None:
        raise HTTPException(status_code=400, detail="当前会话尚未绑定设备")

    ticket = ws_ticket_store.create(
        user_id=auth_context.user.id,
        session_public_id=auth_session.session_id,
        device_public_id=auth_context.device.device_id,
    )
    return {
        "ticket": ticket.token,
        "expires_at": ticket.expires_at.isoformat(),
        "device_id": auth_context.device.device_id,
    }
