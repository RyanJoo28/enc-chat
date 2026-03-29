from collections import deque
from datetime import timedelta

from app.e2ee.service import rate_limit_window_exceeded, utcnow, ws_ticket_store


def test_ws_ticket_is_single_use():
    ticket = ws_ticket_store.create(user_id=1, session_public_id="session-1", device_public_id="device-1")

    consumed = ws_ticket_store.consume(ticket.token)

    assert consumed is not None
    assert consumed.token == ticket.token
    assert ws_ticket_store.consume(ticket.token) is None


def test_expired_ws_ticket_cannot_be_consumed():
    ticket = ws_ticket_store.create(user_id=1, session_public_id="session-1", device_public_id="device-1")
    ws_ticket_store._tickets[ticket.token].expires_at = utcnow() - timedelta(seconds=1)

    assert ws_ticket_store.consume(ticket.token) is None


def test_rate_limit_window_exceeded_blocks_after_limit():
    timestamps = deque()

    blocked = False
    for index in range(121):
        blocked = rate_limit_window_exceeded(timestamps, float(index) / 10.0)

    assert blocked is True
