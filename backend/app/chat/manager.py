import json
from dataclasses import dataclass
from typing import Dict, List

from fastapi import WebSocket


@dataclass
class ActiveConnection:
    websocket: WebSocket
    device_id: str | None = None


class ChatManager:
    """管理在线连接与消息广播。"""

    def __init__(self):
        self.active_connections: Dict[int, List[ActiveConnection]] = {}

    async def _send_presence_snapshot(self, user_id: int, websocket: WebSocket):
        """向新连接发送当前已在线用户快照。"""
        online_user_ids = [online_user_id for online_user_id in self.active_connections.keys() if online_user_id != user_id]
        await websocket.send_text(json.dumps({
            "type": "presence.snapshot",
            "online_user_ids": online_user_ids,
        }))

    async def connect(self, user_id: int, websocket: WebSocket, device_id: str | None = None):
        await websocket.accept()
        was_offline = user_id not in self.active_connections
        self.active_connections.setdefault(user_id, []).append(ActiveConnection(websocket=websocket, device_id=device_id))
        try:
            await self._send_presence_snapshot(user_id, websocket)
        except Exception:
            self._remove_connection(user_id, websocket)
            raise
        if was_offline:
            await self.broadcast_status(user_id, "online")

    def _remove_connection(self, user_id: int, websocket: WebSocket) -> bool:
        """移除单个连接，并返回该用户是否已完全离线。"""
        connections = self.active_connections.get(user_id)
        if not connections:
            return False

        for connection in list(connections):
            if connection.websocket == websocket:
                connections.remove(connection)
                break

        if connections:
            return False

        del self.active_connections[user_id]
        return True

    def disconnect(self, user_id: int, websocket: WebSocket) -> bool:
        return self._remove_connection(user_id, websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_to_user(self, user_id: int, message: str):
        """向指定用户的所有在线连接发送消息。"""
        for connection in list(self.active_connections.get(user_id, [])):
            try:
                await connection.websocket.send_text(message)
            except Exception:
                if self._remove_connection(user_id, connection.websocket):
                    await self.broadcast_status(user_id, "offline")

    async def disconnect_device(self, user_id: int, device_id: str, *, close_code: int = 1008, reason: str = "device_revoked") -> bool:
        """断开指定设备的所有在线连接。"""
        connections = list(self.active_connections.get(user_id, []))
        removed_any = False
        user_went_offline = False

        for connection in connections:
            if connection.device_id != device_id:
                continue

            try:
                await connection.websocket.close(code=close_code, reason=reason)
            except Exception:
                pass

            if self._remove_connection(user_id, connection.websocket):
                user_went_offline = True
            removed_any = True

        if user_went_offline:
            await self.broadcast_status(user_id, "offline")

        return removed_any

    async def broadcast_status(self, user_id: int, status: str):
        """向所有在线用户广播某人的状态变更。"""
        message = json.dumps({
            "type": "user_status",
            "user_id": user_id,
            "status": status
        })

        offline_users = set()
        for target_user_id, connections in list(self.active_connections.items()):
            for connection in list(connections):
                try:
                    await connection.websocket.send_text(message)
                except Exception:
                    if self._remove_connection(target_user_id, connection.websocket):
                        offline_users.add(target_user_id)

        for offline_user_id in offline_users:
            if offline_user_id != user_id or status != "offline":
                await self.broadcast_status(offline_user_id, "offline")

    async def broadcast_group_created(self, group_id: int, group_name: str, member_ids: list[int]):
        """通知成员刷新群组列表。"""
        payload = json.dumps({
            "type": "group_created",
            "group_id": group_id,
            "group_name": group_name
        })

        for uid in member_ids:
            await self.send_to_user(uid, payload)

    async def broadcast_user_updated(
            self,
            user_id: int,
            old_username: str,
            new_username: str,
            recipient_ids: set[int] | None = None,
            avatar: str | None = None
    ):
        """向指定在线用户广播用户资料变更。"""
        payload = json.dumps({
            "type": "user_updated",
            "user_id": user_id,
            "old_username": old_username,
            "username": new_username,
            "avatar": avatar
        })

        offline_users = set()
        target_ids = recipient_ids if recipient_ids is not None else set(self.active_connections.keys())
        for target_user_id in list(target_ids):
            connections = list(self.active_connections.get(target_user_id, []))
            for connection in list(connections):
                try:
                    await connection.websocket.send_text(payload)
                except Exception:
                    if self._remove_connection(target_user_id, connection.websocket):
                        offline_users.add(target_user_id)

        for offline_user_id in offline_users:
            await self.broadcast_status(offline_user_id, "offline")

    async def broadcast_group_access_updated(self, user_ids: list[int], group_id: int):
        """通知相关用户刷新群邀请/入群申请状态。"""
        payload = json.dumps({
            "type": "group_access_updated",
            "group_id": group_id
        })

        for user_id in user_ids:
            await self.send_to_user(user_id, payload)

    async def broadcast_group_epoch_changed(self, user_ids: list[int], group_id: int, epoch: int):
        """通知相关用户刷新群 sender key epoch。"""
        payload = json.dumps({
            "type": "group_epoch_changed",
            "group_id": group_id,
            "epoch": epoch
        })

        for user_id in user_ids:
            await self.send_to_user(user_id, payload)

    async def broadcast_friend_access_updated(self, user_a_id: int, user_b_id: int):
        """通知双方刷新好友请求/关系状态。"""
        await self.send_to_user(user_a_id, json.dumps({
            "type": "friend_access_updated",
            "peer_id": user_b_id
        }))
        await self.send_to_user(user_b_id, json.dumps({
            "type": "friend_access_updated",
            "peer_id": user_a_id
        }))

    async def broadcast_device_added(self, user_ids: list[int] | set[int], payload: dict | None = None):
        """通知相关用户有新设备加入，以便触发 sender key 重新分发。"""
        encoded = json.dumps({
            "type": "device.added",
            **(payload or {}),
        }, ensure_ascii=False)
        for user_id in set(user_ids):
            await self.send_to_user(user_id, encoded)

    async def broadcast_device_revoked(self, user_ids: list[int] | set[int], payload: dict | None = None):
        """通知相关用户某个设备已撤销。"""
        encoded = json.dumps({
            "type": "device.revoked",
            **(payload or {}),
        }, ensure_ascii=False)
        for user_id in set(user_ids):
            await self.send_to_user(user_id, encoded)

manager = ChatManager()
