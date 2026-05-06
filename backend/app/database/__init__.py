import os
from hashlib import sha256
import re

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from .config import get_database_url
from .models import Base, ACTIVE_BOOTSTRAP_TABLES


SQLALCHEMY_DATABASE_URL = get_database_url()
SKIP_RUNTIME_BOOTSTRAP = os.getenv("ALEMBIC_RUNNING") == "1"

# 引擎与会话工厂
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "pool_size": 100,
    "max_overflow": 200,
}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
if not SKIP_RUNTIME_BOOTSTRAP:
    Base.metadata.create_all(bind=engine, tables=ACTIVE_BOOTSTRAP_TABLES)


def _ensure_current_columns() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements = []

    # messages_v2 column additions
    if "messages_v2" in table_names:
        message_columns = {column["name"] for column in inspector.get_columns("messages_v2")}
        index_names = {index.get("name") for index in inspector.get_indexes("messages_v2")}
        if "is_recalled" not in message_columns:
            statements.append(
                "ALTER TABLE messages_v2 ADD COLUMN is_recalled TINYINT(1) NOT NULL DEFAULT 0"
            )
        if "recalled_at" not in message_columns:
            statements.append(
                "ALTER TABLE messages_v2 ADD COLUMN recalled_at DATETIME NULL"
            )
        if "recalled_by_user_id" not in message_columns:
            statements.append(
                "ALTER TABLE messages_v2 ADD COLUMN recalled_by_user_id INTEGER NULL"
            )
        if "ix_messages_v2_is_recalled" not in index_names:
            statements.append(
                "CREATE INDEX ix_messages_v2_is_recalled ON messages_v2 (is_recalled)"
            )

    # auth_sessions ip_address column resize for encrypted storage
    if "auth_sessions" in table_names:
        auth_columns = {c["name"]: c for c in inspector.get_columns("auth_sessions")}
        ip_col = auth_columns.get("ip_address")
        if ip_col and isinstance(ip_col.get("type"), str):
            col_type = ip_col["type"].upper()
            if "VARCHAR" in col_type:
                try:
                    length_str = col_type.split("(")[1].split(")")[0]
                    if int(length_str) < 200:
                        statements.append(
                            "ALTER TABLE auth_sessions MODIFY COLUMN ip_address VARCHAR(200) NULL"
                        )
                except (ValueError, IndexError):
                    pass

    # group_join_requests note column resize for encrypted storage
    if "group_join_requests" in table_names:
        gjr_columns = {c["name"]: c for c in inspector.get_columns("group_join_requests")}
        note_col = gjr_columns.get("note")
        if note_col and isinstance(note_col.get("type"), str):
            col_type = note_col["type"].upper()
            if "VARCHAR" in col_type:
                try:
                    length_str = col_type.split("(")[1].split(")")[0]
                    if int(length_str) < 200:
                        statements.append(
                            "ALTER TABLE group_join_requests MODIFY COLUMN note VARCHAR(1024) NULL"
                        )
                except (ValueError, IndexError):
                    pass

    # users password column resize for encrypted storage
    if "users" in table_names:
        user_columns = {c["name"]: c for c in inspector.get_columns("users")}
        pwd_col = user_columns.get("password")
        if pwd_col and isinstance(pwd_col.get("type"), str):
            col_type = pwd_col["type"].upper()
            if "VARCHAR" in col_type:
                try:
                    length_str = col_type.split("(")[1].split(")")[0]
                    if int(length_str) < 200:
                        statements.append(
                            "ALTER TABLE users MODIFY COLUMN password VARCHAR(512) NOT NULL"
                        )
                except (ValueError, IndexError):
                    pass

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


if not SKIP_RUNTIME_BOOTSTRAP:
    _ensure_current_columns()


def _hash_legacy_token_blacklist() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "token_blacklist" not in table_names:
        return

    _HEX64 = re.compile(r"^[0-9a-f]{64}$")
    with SessionLocal() as db:
        try:
            rows = db.execute(text("SELECT id, token FROM token_blacklist")).fetchall()
            updates = []
            for row_id, stored_token in rows:
                if stored_token and not _HEX64.match(stored_token):
                    updates.append((sha256(stored_token.encode()).hexdigest(), row_id))
            if updates:
                for token_hash, row_id in updates:
                    db.execute(
                        text("UPDATE OR IGNORE token_blacklist SET token = :hash WHERE id = :rid"),
                        {"hash": token_hash, "rid": row_id},
                    )
                db.commit()
        except Exception:
            db.rollback()


if not SKIP_RUNTIME_BOOTSTRAP:
    _hash_legacy_token_blacklist()


def get_db():
    """为请求提供数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
