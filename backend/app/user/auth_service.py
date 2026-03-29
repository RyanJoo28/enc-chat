import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..database.models import AuthSession, Device, User
from ..settings import (
    ACCESS_TOKEN_TTL_MINUTES,
    FEATURE_FLAGS,
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_SAMESITE,
    REFRESH_COOKIE_SECURE,
    REFRESH_SESSION_TTL_DAYS,
)
from .manager import ALGORITHM, SECRET_KEY


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _cookie_expiry(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _new_session_public_id() -> str:
    return str(uuid.uuid4())


def _refresh_cookie_samesite() -> str:
    if REFRESH_COOKIE_SAMESITE in {"lax", "strict", "none"}:
        return REFRESH_COOKIE_SAMESITE
    return "lax"


def _refresh_expiry() -> datetime:
    return utcnow() + timedelta(days=REFRESH_SESSION_TTL_DAYS)


def _access_expiry() -> datetime:
    return utcnow() + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES)


def set_refresh_cookie(response: Response, refresh_token: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite=_refresh_cookie_samesite(),
        expires=_cookie_expiry(expires_at),
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite=_refresh_cookie_samesite(),
    )


def get_refresh_token_from_request(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE_NAME)


def _build_access_payload(user: User, auth_session: AuthSession, device: Device | None) -> dict:
    expires_at = _access_expiry()
    return {
        "sub": user.username,
        "user_id": user.id,
        "sid": auth_session.session_id,
        "device_id": device.device_id if device else None,
        "session_version": user.session_version,
        "type": "access",
        "exp": expires_at,
    }


def create_access_token(user: User, auth_session: AuthSession, device: Device | None = None) -> str:
    return jwt.encode(_build_access_payload(user, auth_session, device), SECRET_KEY, algorithm=ALGORITHM)


def get_active_session_device(db: Session, auth_session: AuthSession) -> Device | None:
    if auth_session.device_id is None:
        return None

    return db.query(Device).filter(
        Device.id == auth_session.device_id,
        Device.user_id == auth_session.user_id,
        Device.is_active.is_(True),
        Device.revoked_at.is_(None),
    ).first()


def build_auth_response_payload(db: Session, user: User, auth_session: AuthSession) -> dict:
    device = get_active_session_device(db, auth_session)
    access_token = create_access_token(user, auth_session, device)
    return {
        "token": access_token,
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "avatar": user.avatar,
        "user_id": user.id,
        "e2ee_enabled": user.e2ee_enabled,
        "device_id": device.device_id if device else None,
        "session_id": auth_session.session_id,
        "feature_flags": FEATURE_FLAGS.as_dict(),
    }


def create_auth_session(
        db: Session,
        user: User,
        *,
        user_agent: str | None,
        ip_address: str | None,
        device: Device | None = None,
) -> tuple[AuthSession, str]:
    refresh_token = _new_refresh_token()
    auth_session = AuthSession(
        session_id=_new_session_public_id(),
        user_id=user.id,
        device_id=device.id if device else None,
        refresh_token_hash=_hash_token(refresh_token),
        session_family_id=_new_session_public_id(),
        user_session_version=user.session_version,
        status="active",
        user_agent=user_agent,
        ip_address=ip_address,
        last_used_at=utcnow(),
        expires_at=_refresh_expiry(),
    )
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    return auth_session, refresh_token


def get_auth_session_by_refresh_token(db: Session, refresh_token: str | None) -> AuthSession | None:
    if not refresh_token:
        return None

    return db.query(AuthSession).filter(AuthSession.refresh_token_hash == _hash_token(refresh_token)).first()


def get_auth_session_by_public_id(db: Session, session_public_id: str | None) -> AuthSession | None:
    if not session_public_id:
        return None

    return db.query(AuthSession).filter(AuthSession.session_id == session_public_id).first()


def is_session_active(auth_session: AuthSession, user: User | None = None) -> bool:
    if auth_session.status != "active":
        return False

    expires_at = _normalize_expiry(auth_session.expires_at)
    if expires_at is None or expires_at <= utcnow().replace(tzinfo=None):
        return False

    if user is not None and auth_session.user_session_version != user.session_version:
        return False

    return True


def ensure_active_session(auth_session: AuthSession | None, user: User | None = None) -> AuthSession:
    if auth_session is None or not is_session_active(auth_session, user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return auth_session


def rotate_auth_session(
        db: Session,
        auth_session: AuthSession,
        *,
        user_agent: str | None,
        ip_address: str | None,
) -> tuple[AuthSession, str]:
    refresh_token = _new_refresh_token()
    new_session = AuthSession(
        session_id=_new_session_public_id(),
        user_id=auth_session.user_id,
        device_id=auth_session.device_id,
        refresh_token_hash=_hash_token(refresh_token),
        session_family_id=auth_session.session_family_id,
        user_session_version=auth_session.user_session_version,
        status="active",
        user_agent=user_agent or auth_session.user_agent,
        ip_address=ip_address or auth_session.ip_address,
        last_used_at=utcnow(),
        expires_at=_refresh_expiry(),
        rotated_from_session_id=auth_session.id,
    )
    db.add(new_session)
    db.flush()

    auth_session.status = "rotated"
    auth_session.revoked_at = utcnow()
    auth_session.last_used_at = utcnow()
    auth_session.replaced_by_session_id = new_session.id

    db.commit()
    db.refresh(new_session)
    return new_session, refresh_token


def revoke_auth_session(db: Session, auth_session: AuthSession | None, status_value: str = "revoked") -> None:
    if auth_session is None or auth_session.status == status_value:
        return

    auth_session.status = status_value
    auth_session.revoked_at = utcnow()
    auth_session.last_used_at = utcnow()
    db.commit()


def revoke_user_sessions(db: Session, user_id: int, *, device_db_id: int | None = None) -> int:
    sessions = db.query(AuthSession).filter(
        AuthSession.user_id == user_id,
        AuthSession.status == "active",
    )
    if device_db_id is not None:
        sessions = sessions.filter(AuthSession.device_id == device_db_id)

    session_rows = sessions.all()
    now = utcnow()
    for auth_session in session_rows:
        auth_session.status = "revoked"
        auth_session.revoked_at = now
        auth_session.last_used_at = now

    if session_rows:
        db.commit()

    return len(session_rows)


def mark_session_used(db: Session, auth_session: AuthSession, *, ip_address: str | None = None, user_agent: str | None = None) -> None:
    auth_session.last_used_at = utcnow()
    if ip_address:
        auth_session.ip_address = ip_address
    if user_agent:
        auth_session.user_agent = user_agent
    db.commit()


def bind_session_to_device(db: Session, auth_session: AuthSession, device: Device) -> AuthSession:
    auth_session.device_id = device.id
    auth_session.last_used_at = utcnow()
    db.commit()
    db.refresh(auth_session)
    return auth_session


@dataclass
class RefreshContext:
    user: User
    auth_session: AuthSession


def resolve_refresh_context(db: Session, request: Request) -> RefreshContext:
    refresh_token = get_refresh_token_from_request(request)
    auth_session = get_auth_session_by_refresh_token(db, refresh_token)
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新会话不存在")

    user = db.query(User).filter(User.id == auth_session.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新会话不存在")

    ensure_active_session(auth_session, user)
    return RefreshContext(user=user, auth_session=auth_session)
