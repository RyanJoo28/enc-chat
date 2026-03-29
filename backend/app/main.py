import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .chat import access_routes as chat_access_routes
from .chat import routes as chat_routes
from .database import SessionLocal, crud
from .database.models import Group, User
from .e2ee import routes as e2ee_routes
from .e2ee import ws_routes as e2ee_ws_routes
from .settings import (
    ALLOWED_HOSTS,
    API_CONTENT_SECURITY_POLICY,
    AVATAR_DIR,
    CORS_ALLOWED_ORIGIN_REGEX,
    CORS_ALLOWED_ORIGINS,
    FEATURE_FLAGS,
    GROUP_AVATAR_DIR,
    LOG_FILE_PATH,
    LOG_LEVEL,
)
from .user import friend_routes
from .user import routes as user_routes
from .utils import encryption
from .utils.limiter import limiter
from .utils.log_utils import build_log_payload, log_event

# 日志配置
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE_PATH), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

# 应用初始化
app = FastAPI(
    title="加密聊天管理系统",
    description="基于 Python + Vue.js 的聊天加密管理系统毕业设计",
    version="1.0.0"
)

# 限流
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# 安全响应头
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = API_CONTENT_SECURITY_POLICY
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "0"
    return response


# Host 校验
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_origin_regex=CORS_ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(build_log_payload(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        error=str(exc),
    ))
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请联系管理员。"}
    )


# 启动清理
def migrate_encrypted_metadata_fields() -> tuple[int, int]:
    """将历史明文元数据迁移为加密存储，并补齐哈希索引列。"""
    db = SessionLocal()
    migrated_users = 0
    migrated_groups = 0

    try:
        for user in db.query(User).all():
            changed = False
            username_value = user.username
            if encryption.is_encrypted_db_text(user._username) and username_value == encryption.DB_DECRYPTION_FAILED_PLACEHOLDER:
                log_event(logger, logging.WARNING, "user_metadata_migration_skipped_decrypt_failure", user_id=user.id)
                continue

            expected_username_hash = encryption.metadata_hash(username_value, case_insensitive=True, namespace="user.username")
            if not encryption.is_encrypted_db_text(user._username) or user.username_hash != expected_username_hash:
                user.username = username_value
                changed = True

            avatar_value = user.avatar
            if user._avatar and encryption.is_encrypted_db_text(user._avatar) and avatar_value == encryption.DB_DECRYPTION_FAILED_PLACEHOLDER:
                log_event(logger, logging.WARNING, "user_avatar_migration_skipped_decrypt_failure", user_id=user.id)
            elif user._avatar and not encryption.is_encrypted_db_text(user._avatar):
                user.avatar = avatar_value
                changed = True

            expected_user_tokens = set(encryption.build_blind_index_hashes(username_value, namespace="user.search"))
            if crud.get_user_search_token_hashes(db, user.id) != expected_user_tokens:
                crud.sync_user_search_tokens(db, user.id, username_value)
                changed = True

            if changed:
                migrated_users += 1

        for group in db.query(Group).all():
            changed = False
            group_name = group.name
            if encryption.is_encrypted_db_text(group._name) and group_name == encryption.DB_DECRYPTION_FAILED_PLACEHOLDER:
                log_event(logger, logging.WARNING, "group_metadata_migration_skipped_decrypt_failure", group_id=group.id)
                continue

            if not encryption.is_encrypted_db_text(group._name):
                group.name = group_name
                changed = True

            group_avatar = group.avatar
            if group._avatar and encryption.is_encrypted_db_text(group._avatar) and group_avatar == encryption.DB_DECRYPTION_FAILED_PLACEHOLDER:
                log_event(logger, logging.WARNING, "group_avatar_migration_skipped_decrypt_failure", group_id=group.id)
            elif group._avatar and not encryption.is_encrypted_db_text(group._avatar):
                group.avatar = group_avatar
                changed = True

            expected_group_tokens = set(encryption.build_blind_index_hashes(group_name, namespace="group.search"))
            if crud.get_group_search_token_hashes(db, group.id) != expected_group_tokens:
                crud.sync_group_search_tokens(db, group.id, group_name)
                changed = True

            if changed:
                migrated_groups += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return migrated_users, migrated_groups


@app.on_event("startup")
async def run_startup_maintenance():
    user_avatar_scanned, user_avatar_migrated = encryption.migrate_plaintext_files_in_directory(AVATAR_DIR)
    group_avatar_scanned, group_avatar_migrated = encryption.migrate_plaintext_files_in_directory(GROUP_AVATAR_DIR)
    if user_avatar_migrated or group_avatar_migrated:
        log_event(
            logger,
            logging.INFO,
            "avatar_storage_migration_completed",
            user_avatar_migrated=user_avatar_migrated,
            user_avatar_scanned=user_avatar_scanned,
            group_avatar_migrated=group_avatar_migrated,
            group_avatar_scanned=group_avatar_scanned,
        )

    migrated_users, migrated_groups = migrate_encrypted_metadata_fields()
    if migrated_users or migrated_groups:
        log_event(
            logger,
            logging.INFO,
            "metadata_encryption_sync_completed",
            migrated_users=migrated_users,
            migrated_groups=migrated_groups,
        )

    log_event(
        logger,
        logging.INFO,
        "app_startup_completed",
        feature_flags=FEATURE_FLAGS.as_dict(),
    )


# 路由注册
app.include_router(user_routes.router, prefix="/api/user", tags=["User Module"])
app.include_router(friend_routes.router, prefix="/api/user", tags=["Friend Module"])
app.include_router(chat_routes.router, prefix="/api/chat", tags=["Chat Module"])
app.include_router(chat_access_routes.router, prefix="/api/chat", tags=["Group Access"])
if FEATURE_FLAGS.e2ee_private_enabled or FEATURE_FLAGS.e2ee_group_enabled:
    app.include_router(e2ee_routes.router, prefix="/api/e2ee", tags=["E2EE"])
    app.include_router(e2ee_ws_routes.router, prefix="/api/e2ee", tags=["E2EE WS"])

@app.get("/")
async def root():
    return {"message": "System is running. Welcome to Encrypted Chat API."}
