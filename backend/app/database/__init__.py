import os

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
    if "messages_v2" not in table_names:
        return

    message_columns = {column["name"] for column in inspector.get_columns("messages_v2")}
    index_names = {index.get("name") for index in inspector.get_indexes("messages_v2")}
    statements = []
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

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


if not SKIP_RUNTIME_BOOTSTRAP:
    _ensure_current_columns()


def get_db():
    """为请求提供数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
