import json
import logging
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from ..chat.manager import manager as chat_manager
from ..database import SessionLocal, crud
from ..database.models import Device
from ..settings import WS_MAX_MESSAGE_BYTES
from ..user.auth_service import ensure_active_session, get_auth_session_by_public_id, mark_session_used
from ..utils.log_utils import build_log_payload
from .service import ack_message_for_device, create_group_message, create_private_message, is_allowed_ws_origin, naive_utcnow, rate_limit_window_exceeded, ws_ticket_store


router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def e2ee_chat_endpoint(websocket: WebSocket, ticket: str = Query(...)):
    """通过一次性 ticket 建立 e2ee_v1 WebSocket 通道。"""
    origin = websocket.headers.get("origin")
    if not is_allowed_ws_origin(origin):
        logger.warning(build_log_payload("e2ee_ws_origin_rejected", origin=origin))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    ticket_payload = ws_ticket_store.consume(ticket)
    if ticket_payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    auth_db = SessionLocal()
    try:
        user = crud.get_user(auth_db, ticket_payload.user_id)
        auth_session = get_auth_session_by_public_id(auth_db, ticket_payload.session_public_id)
        if user is None or auth_session is None:
            raise PermissionError("invalid ticket context")

        ensure_active_session(auth_session, user)
        device = auth_db.query(Device).filter(
            Device.id == auth_session.device_id,
            Device.user_id == user.id,
            Device.device_id == ticket_payload.device_public_id,
            Device.is_active.is_(True),
            Device.revoked_at.is_(None),
        ).first()
        if device is None:
            raise PermissionError("invalid device binding")

        device.last_seen_at = naive_utcnow()
        auth_db.commit()
        mark_session_used(auth_db, auth_session)
    except Exception as exc:
        logger.exception(build_log_payload("e2ee_ws_auth_failed", error=str(exc)))
        auth_db.close()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    finally:
        if auth_db.is_active:
            auth_db.close()

    user_id = ticket_payload.user_id
    current_device_id = ticket_payload.device_public_id
    await chat_manager.connect(user_id, websocket, current_device_id)
    message_timestamps = deque()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                preview = json.loads(data)
                msg_type = preview.get("type", "unknown")
            except (json.JSONDecodeError, TypeError):
                msg_type = "invalid_json"
            logger.info(build_log_payload(
                "ws_message_received",
                ws_payload_type=msg_type,
                ws_payload_bytes=len(data.encode("utf-8")),
                user_id=user_id,
                device_id=current_device_id,
            ))
            if len(data.encode("utf-8")) > WS_MAX_MESSAGE_BYTES:
                await websocket.send_text(json.dumps({"type": "error", "detail": "消息过大"}, ensure_ascii=False))
                await websocket.close(code=status.WS_1009_MESSAGE_TOO_BIG)
                return

            if rate_limit_window_exceeded(message_timestamps, time.monotonic()):
                await websocket.send_text(json.dumps({"type": "error", "detail": "消息过于频繁"}, ensure_ascii=False))
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            db = SessionLocal()
            try:
                payload = json.loads(data)
                payload_type = payload.get("type")
                if payload_type == "message.send":
                    sender = crud.get_user(db, user_id)
                    sender_device = db.query(Device).filter(
                        Device.user_id == user_id,
                        Device.device_id == current_device_id,
                        Device.is_active.is_(True),
                        Device.revoked_at.is_(None),
                    ).first()
                    if sender is None or sender_device is None:
                        await websocket.send_text(json.dumps({"type": "error", "detail": "当前会话尚未绑定设备"}, ensure_ascii=False))
                        continue

                    if payload.get("chat_type") == "private":
                        try:
                            target_user_id = int(payload.get("to"))
                        except (TypeError, ValueError):
                            raise HTTPException(status_code=400, detail="消息格式无效")

                        result = create_private_message(
                            db,
                            sender=sender,
                            sender_device=sender_device,
                            target_user_id=target_user_id,
                            client_message_id=payload.get("client_message_id"),
                            message_type=payload.get("msg_type", "text"),
                            packets=payload.get("packets", []),
                            attachment_blob_ids=payload.get("attachment_blob_ids", []),
                        )
                    elif payload.get("chat_type") == "group":
                        try:
                            target_group_id = int(payload.get("to"))
                            group_epoch = int(payload.get("group_epoch"))
                        except (TypeError, ValueError):
                            raise HTTPException(status_code=400, detail="消息格式无效")

                        result = create_group_message(
                            db,
                            sender=sender,
                            sender_device=sender_device,
                            group_id=target_group_id,
                            group_epoch=group_epoch,
                            client_message_id=payload.get("client_message_id"),
                            message_type=payload.get("msg_type", "text"),
                            packets=payload.get("packets", []),
                            attachment_blob_ids=payload.get("attachment_blob_ids", []),
                        )
                    else:
                        raise HTTPException(status_code=400, detail="消息格式无效")

                    for target_user_id, event_payload in result["events"].items():
                        await chat_manager.send_to_user(target_user_id, json.dumps(event_payload, ensure_ascii=False))
                elif payload_type == "message.ack":
                    try:
                        message_id = int(payload.get("message_id"))
                    except (TypeError, ValueError):
                        raise HTTPException(status_code=400, detail="消息格式无效")

                    current_device = db.query(Device).filter(
                        Device.user_id == user_id,
                        Device.device_id == current_device_id,
                        Device.is_active.is_(True),
                        Device.revoked_at.is_(None),
                    ).first()
                    if current_device is None:
                        await websocket.send_text(json.dumps({"type": "error", "detail": "当前会话尚未绑定设备"}, ensure_ascii=False))
                        continue

                    delivery_event = ack_message_for_device(
                        db,
                        current_user_id=user_id,
                        device=current_device,
                        message_id=message_id,
                        status_value=payload.get("status", "delivered"),
                    )
                    await chat_manager.send_to_user(
                        delivery_event["sender_user_id"],
                        json.dumps({"type": "message.delivery", **delivery_event}, ensure_ascii=False),
                    )
                else:
                    raise HTTPException(status_code=400, detail="消息格式无效")
            except HTTPException as exc:
                await websocket.send_text(json.dumps({"type": "error", "detail": exc.detail}, ensure_ascii=False))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "消息格式无效"}, ensure_ascii=False))
            finally:
                db.close()
    except WebSocketDisconnect:
        if chat_manager.disconnect(user_id, websocket):
            await chat_manager.broadcast_status(user_id, "offline")
    except Exception as exc:
        logger.exception(build_log_payload("e2ee_ws_runtime_failed", user_id=user_id, error=str(exc)))
        if chat_manager.disconnect(user_id, websocket):
            await chat_manager.broadcast_status(user_id, "offline")
