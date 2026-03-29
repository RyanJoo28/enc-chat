from dataclasses import dataclass
from typing import cast

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..database import get_db
from ..database.models import AuthSession, Device, TokenBlacklist, User
from .auth_service import ensure_active_session, get_active_session_device, get_auth_session_by_public_id
from .manager import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login", auto_error=False)
TOKEN_SECRET = cast(str, SECRET_KEY)


@dataclass
class AuthContext:
    user: User
    auth_session: AuthSession | None
    device: Device | None
    token_payload: dict


def resolve_current_user(token: str, db: Session) -> User:
    """根据 Token 校验并返回当前用户。"""
    return resolve_auth_context(token, db).user


def resolve_auth_context(token: str, db: Session) -> AuthContext:
    """根据访问令牌返回当前用户、会话和设备。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 注销后的 Token 会被加入黑名单，后续请求直接拒绝。
    blacklisted = db.query(TokenBlacklist).filter(TokenBlacklist.token == token).first()
    if blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已失效 (已注销)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, TOKEN_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        session_public_id = payload.get("sid")
        if payload.get("type") != "access" or user_id is None or session_public_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    device = None
    auth_session = None
    auth_session = get_auth_session_by_public_id(db, session_public_id)
    ensure_active_session(auth_session, user)
    device = get_active_session_device(db, auth_session)
    token_device_id = payload.get("device_id")
    if device is not None and token_device_id != device.device_id:
        raise credentials_exception
    if device is None and token_device_id is not None:
        raise credentials_exception

    return AuthContext(user=user, auth_session=auth_session, device=device, token_payload=payload)


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """HTTP 请求依赖：校验 JWT 并返回当前用户。"""
    return resolve_current_user(token, db)


async def get_auth_context(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """HTTP 请求依赖：校验访问令牌并返回认证上下文。"""
    return resolve_auth_context(token, db)


async def get_optional_auth_context(token: str | None = Depends(optional_oauth2_scheme), db: Session = Depends(get_db)):
    """可选认证依赖，用于支持仅依赖 refresh cookie 的注销流程。"""
    if not token:
        return None
    try:
        return resolve_auth_context(token, db)
    except HTTPException:
        return None
