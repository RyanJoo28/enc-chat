import json
import logging
from typing import Any


def _normalize_log_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, dict):
        return {str(key): _normalize_log_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_normalize_log_value(item) for item in value]

    return str(value)


def build_log_payload(event: str, **fields: Any) -> str:
    payload = {"event": event}
    payload.update({key: _normalize_log_value(value) for key, value in fields.items()})
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    logger.log(level, build_log_payload(event, **fields))
