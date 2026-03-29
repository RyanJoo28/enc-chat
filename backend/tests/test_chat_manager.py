import asyncio
import json

from app.chat.manager import ChatManager


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, message: str):
        self.messages.append(message)

    async def close(self, code: int = 1000, reason: str | None = None):
        self.closed = True
        self.close_code = code
        self.close_reason = reason


def test_new_connection_receives_online_presence_snapshot():
    async def scenario():
        manager = ChatManager()
        first_socket = FakeWebSocket()
        second_socket = FakeWebSocket()

        await manager.connect(1, first_socket, "device-1")
        await manager.connect(2, second_socket, "device-2")

        snapshot_payload = json.loads(second_socket.messages[0])
        assert snapshot_payload == {
            "type": "presence.snapshot",
            "online_user_ids": [1],
        }

        status_payload = json.loads(first_socket.messages[-1])
        assert status_payload == {
            "type": "user_status",
            "user_id": 2,
            "status": "online",
        }

    asyncio.run(scenario())


def test_disconnect_device_only_closes_matching_socket():
    async def scenario():
        manager = ChatManager()
        target_socket = FakeWebSocket()
        other_socket = FakeWebSocket()

        await manager.connect(1, target_socket, "device-a")
        await manager.connect(1, other_socket, "device-b")

        disconnected = await manager.disconnect_device(1, "device-a", close_code=4001, reason="device_revoked")

        assert disconnected is True
        assert target_socket.closed is True
        assert target_socket.close_code == 4001
        assert target_socket.close_reason == "device_revoked"
        assert other_socket.closed is False
        assert len(manager.active_connections[1]) == 1
        assert manager.active_connections[1][0].device_id == "device-b"

    asyncio.run(scenario())
