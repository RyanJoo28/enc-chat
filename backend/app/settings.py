import os
import socket
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


# 统一管理后端运行时路径，便于本地运行和 Docker 复用同一套代码。

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _split_csv_env(env_name: str, default: str = "") -> list[str]:
    raw_value = os.getenv(env_name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _get_bool_env(env_name: str, default: bool = False) -> bool:
    raw_value = os.getenv(env_name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(env_name: str, default: int) -> int:
    raw_value = os.getenv(env_name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def _default_allowed_hosts() -> str:
    hosts = {
        "localhost",
        "127.0.0.1",
        "[::1]",
        "0.0.0.0",
        "testserver",
        "*.localhost",
    }

    try:
        hostname = socket.gethostname()
        if hostname:
            hosts.add(hostname)
            for address in socket.gethostbyname_ex(hostname)[2]:
                if address:
                    hosts.add(address)
    except OSError:
        pass

    return ",".join(sorted(hosts))


def _resolve_root(value):
    """解析应用根目录配置。"""
    if not value:
        return BACKEND_ROOT

    path = Path(value)
    return path if path.is_absolute() else BACKEND_ROOT / path


def _resolve_data_path(env_name, default_name):
    """解析运行时数据目录下的文件或子目录。"""
    configured = os.getenv(env_name)
    if configured:
        # 显式配置的相对路径仍相对后端根目录解析，兼容现有本地目录习惯。
        path = Path(configured)
        return path if path.is_absolute() else BACKEND_ROOT / path

    return DATA_ROOT / default_name


@dataclass(frozen=True)
class FeatureFlags:
    e2ee_private_enabled: bool
    e2ee_group_enabled: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "e2ee_private_enabled": self.e2ee_private_enabled,
            "e2ee_group_enabled": self.e2ee_group_enabled,
        }


# 默认情况下，上传目录、日志和私钥都派生自 APP_DATA_DIR。
DATA_ROOT = _resolve_root(os.getenv("APP_DATA_DIR"))
UPLOAD_DIR = _resolve_data_path("UPLOAD_DIR", "uploaded_files")
E2EE_ATTACHMENT_DIR = _resolve_data_path("E2EE_ATTACHMENT_DIR", "uploaded_files_v2")
AVATAR_DIR = _resolve_data_path("AVATAR_DIR", "avatars")
GROUP_AVATAR_DIR = _resolve_data_path("GROUP_AVATAR_DIR", "group_avatars")
LOG_FILE_PATH = _resolve_data_path("APP_LOG_PATH", "app.log")
LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()

ALLOWED_HOSTS = _split_csv_env(
    "APP_ALLOWED_HOSTS",
    _default_allowed_hosts()
)

CORS_ALLOWED_ORIGINS = _split_csv_env(
    "APP_CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,https://localhost:3000,http://127.0.0.1:3000,https://127.0.0.1:3000"
)

CORS_ALLOWED_ORIGIN_REGEX = os.getenv(
    "APP_CORS_ALLOWED_ORIGIN_REGEX",
    r"https?://((localhost|127\.0\.0\.1|\[::1\])|(\d{1,3}(?:\.\d{1,3}){3}))(?:\:\d+)?$"
)

API_CONTENT_SECURITY_POLICY = os.getenv(
    "APP_API_CONTENT_SECURITY_POLICY",
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

FEATURE_FLAGS = FeatureFlags(
    e2ee_private_enabled=_get_bool_env("E2EE_PRIVATE_ENABLED", default=False),
    e2ee_group_enabled=_get_bool_env("E2EE_GROUP_ENABLED", default=False),
)

ACCESS_TOKEN_TTL_MINUTES = _get_int_env("ACCESS_TOKEN_TTL_MINUTES", 15)
REFRESH_SESSION_TTL_DAYS = _get_int_env("REFRESH_SESSION_TTL_DAYS", 30)
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
REFRESH_COOKIE_SECURE = _get_bool_env("REFRESH_COOKIE_SECURE", default=False)
REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", "lax").lower()
WS_TICKET_TTL_SECONDS = _get_int_env("WS_TICKET_TTL_SECONDS", 60)
WS_MAX_MESSAGE_BYTES = _get_int_env("WS_MAX_MESSAGE_BYTES", 1024 * 1024 * 5)
WS_MAX_MESSAGES_PER_MINUTE = _get_int_env("WS_MAX_MESSAGES_PER_MINUTE", 120)
E2EE_ATTACHMENT_MAX_BYTES = _get_int_env("E2EE_ATTACHMENT_MAX_BYTES", 20 * 1024 * 1024)
E2EE_ATTACHMENT_UPLOAD_TTL_MINUTES = _get_int_env("E2EE_ATTACHMENT_UPLOAD_TTL_MINUTES", 60)
