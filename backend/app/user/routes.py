from hashlib import sha256
from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status, File, UploadFile
from sqlalchemy.orm import Session

from ..chat.manager import manager as chat_manager
from ..database import crud, get_db
from ..database.models import TokenBlacklist, User
from ..settings import AVATAR_DIR, FEATURE_FLAGS
from ..utils import encryption
from ..utils.file_validation import validate_file_payload
from ..utils.limiter import get_auth_or_remote_address, limiter
from .auth_service import (
    build_auth_response_payload,
    clear_refresh_cookie,
    create_auth_session,
    get_auth_session_by_refresh_token,
    get_refresh_token_from_request,
    resolve_refresh_context,
    revoke_auth_session,
    revoke_user_sessions,
    rotate_auth_session,
    set_refresh_cookie,
)
from .dependencies import AuthContext, get_auth_context, get_current_user, get_optional_auth_context, optional_oauth2_scheme
from .manager import UserManager
from .schemas import UserChangeName, UserChangePassword, UserCreate, UserLogin

AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_AVATAR_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}
MAX_AVATAR_SIZE = 5 * 1024 * 1024

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """注册用户。"""
    manager = UserManager()
    hashed_pwd = manager.hash_password(user.password)

    try:
        new_user = await manager.create_user(
            db,
            username=user.username,
            password=hashed_pwd
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="注册失败，该用户名可能已存在"
        )

    return {"message": "注册成功", "user_id": new_user.id}


@router.post("/login")
@limiter.limit("500/minute")
async def login(
        request: Request,
        response: Response,
        user: UserLogin,
        db: Session = Depends(get_db)
):
    """登录并创建 refresh session，同时返回短期 access token。"""
    manager = UserManager()

    db_user = await manager.get_user_by_username(db, user.username)

    if not db_user or not manager.verify_password(user.password, db_user.password):
        # 为保持演示体验，认证失败时返回明确文案。
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    auth_session, refresh_token = create_auth_session(
        db,
        db_user,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    set_refresh_cookie(response, refresh_token, auth_session.expires_at)
    return build_auth_response_payload(db, db_user, auth_session)


@router.post("/refresh")
async def refresh_session(
        request: Request,
        response: Response,
        db: Session = Depends(get_db)
):
    """轮换 refresh session，并返回新的短期 access token。"""
    refresh_context = resolve_refresh_context(db, request)
    rotated_session, refresh_token = rotate_auth_session(
        db,
        refresh_context.auth_session,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    set_refresh_cookie(response, refresh_token, rotated_session.expires_at)
    return build_auth_response_payload(db, refresh_context.user, rotated_session)


@router.get("/me")
async def get_me(auth_context: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    """返回当前 access token 绑定的用户与会话摘要。"""
    payload = build_auth_response_payload(db, auth_context.user, auth_context.auth_session) if auth_context.auth_session else {
        "token": None,
        "access_token": None,
        "token_type": "bearer",
        "username": auth_context.user.username,
        "avatar": auth_context.user.avatar,
        "user_id": auth_context.user.id,
        "e2ee_enabled": auth_context.user.e2ee_enabled,
        "device_id": None,
        "session_id": None,
        "feature_flags": FEATURE_FLAGS.as_dict(),
    }
    payload.pop("token", None)
    payload.pop("access_token", None)
    return payload


@router.post("/logout")
async def logout(
        request: Request,
        response: Response,
        token: str | None = Depends(optional_oauth2_scheme),
        auth_context: AuthContext | None = Depends(get_optional_auth_context),
        db: Session = Depends(get_db)
):
    """撤销当前 refresh session，并清理客户端 cookie。"""
    refresh_token = get_refresh_token_from_request(request)
    cookie_session = get_auth_session_by_refresh_token(db, refresh_token)
    revoke_auth_session(db, cookie_session)

    if auth_context and auth_context.auth_session and (cookie_session is None or cookie_session.id != auth_context.auth_session.id):
        revoke_auth_session(db, auth_context.auth_session)

    if token and (auth_context is None or auth_context.auth_session is None):
        token_hash = sha256(token.encode()).hexdigest()
        exists = db.query(TokenBlacklist).filter(TokenBlacklist.token == token_hash).first()
        if not exists:
            db.add(TokenBlacklist(token=token_hash))
            db.commit()

    clear_refresh_cookie(response)
    return {"message": "注销成功"}


@router.get("/all", response_model=List[dict])
async def get_all_users(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """返回当前用户的好友和已有关系用户，避免暴露全量用户目录。"""
    visible_user_ids = (crud.get_friend_ids(db, current_user.id) | crud.get_related_user_ids(db, current_user.id)) - {current_user.id}
    if not visible_user_ids:
        return []

    users = db.query(User).filter(User.id.in_(visible_user_ids)).all()
    users.sort(key=lambda user: (encryption.normalize_search_text(user.username), user.id))

    return [
        {"id": user.id, "username": user.username, "avatar": user.avatar}
        for user in users
    ]


@router.get("/search")
@limiter.limit("1200/minute", key_func=get_auth_or_remote_address)
async def search_users(
        request: Request,
        q: str = Query(..., min_length=1),
        limit: int = Query(20, ge=1, le=50),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """按用户名搜索用户。"""
    users = crud.search_users(db, current_user.id, q, limit=limit, offset=offset)
    private_partner_ids = crud.get_private_partner_ids(db, current_user.id)

    has_more = len(users) > limit
    page_items = users[:limit]
    relationship_map = crud.get_friend_relationship_map(db, current_user.id, [user.id for user in page_items])

    return {
        "items": [
            {
                "id": user.id,
                "username": user.username,
                "avatar": user.avatar,
                "is_online": user.id in chat_manager.active_connections,
                "has_conversation": user.id in private_partner_ids,
                "can_start_chat": crud.can_start_private_chat(db, current_user.id, user.id),
                **relationship_map.get(user.id, {"relationship_status": "none", "friend_request_id": None})
            }
            for user in page_items
        ],
        "has_more": has_more,
        "next_offset": offset + len(page_items) if has_more else None
    }


@router.put("/password")
async def change_password(
        data: UserChangePassword,
        response: Response,
        db: Session = Depends(get_db),
        auth_context: AuthContext = Depends(get_auth_context)
):
    """修改密码。"""
    manager = UserManager()
    current_user = auth_context.user
    if not manager.verify_password(data.old_password, current_user.password):
        raise HTTPException(status_code=400, detail="旧密码错误")

    await manager.update_password(db, current_user, data.new_password)
    current_user.session_version += 1
    db.commit()
    revoke_user_sessions(db, current_user.id)
    clear_refresh_cookie(response)
    return {"message": "密码修改成功"}


@router.put("/username")
async def change_username(
        data: UserChangeName,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """修改用户名。"""
    manager = UserManager()
    old_username = current_user.username
    success = await manager.update_username(db, current_user, data.new_username)
    if not success:
        raise HTTPException(status_code=400, detail="用户名已存在")

    related_user_ids = crud.get_related_user_ids(db, current_user.id)
    related_user_ids.add(current_user.id)

    await chat_manager.broadcast_user_updated(
        current_user.id,
        old_username,
        data.new_username,
        related_user_ids,
        avatar=current_user.avatar
    )

    return {"message": "用户名修改成功", "username": data.new_username}


@router.post("/avatar")
async def upload_avatar(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """上传并设置自定义头像。"""
    file.file.seek(0, 2)
    file_size = file.file.tell()
    await file.seek(0)
    if file_size > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=413, detail="文件过大")

    content = await file.read()

    try:
        file_ext = validate_file_payload(file.filename, file.content_type, content, ALLOWED_AVATAR_EXTENSIONS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    random_name = f"{uuid.uuid4().hex}{file_ext}"
    file_path = AVATAR_DIR / random_name
    encrypted_content = encryption.encrypt_file_content(content)

    try:
        with file_path.open("wb") as f:
            f.write(encrypted_content)

        # Remove old avatar file if needed (skipped for simplicity/safety unless robust logic is used)
        
        current_user.avatar = random_name
        db.commit()
    except Exception:
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        raise HTTPException(status_code=500, detail="头像上传失败")

    related_user_ids = crud.get_related_user_ids(db, current_user.id)
    related_user_ids.add(current_user.id)

    await chat_manager.broadcast_user_updated(
        current_user.id,
        current_user.username,
        current_user.username,
        related_user_ids,
        avatar=random_name
    )

    return {"message": "头像上传成功", "avatar": random_name}


@router.get("/avatar/{filename}")
async def get_avatar(filename: str):
    """获取公开访问的头像。"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    file_path = AVATAR_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    with file_path.open("rb") as f:
        stored_data = f.read()

    if stored_data.startswith(encryption.FILE_ENCRYPTION_MAGIC):
        avatar_bytes = encryption.decrypt_file_content(stored_data)
        if not avatar_bytes and stored_data:
            raise HTTPException(status_code=500, detail="头像解密失败")
    else:
        avatar_bytes = stored_data
        try:
            with file_path.open("wb") as f:
                f.write(encryption.encrypt_file_content(stored_data))
        except OSError:
            pass

    media_type = "application/octet-stream"
    lower_name = filename.lower()
    if lower_name.endswith(('.jpg', '.jpeg')):
        media_type = "image/jpeg"
    elif lower_name.endswith('.png'):
        media_type = "image/png"
    elif lower_name.endswith('.gif'):
        media_type = "image/gif"

    return Response(content=avatar_bytes, media_type=media_type)
