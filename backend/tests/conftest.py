import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


TEST_DATA_ROOT = Path(tempfile.mkdtemp(prefix="enc-chat-tests-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(TEST_DATA_ROOT / 'test.db').as_posix()}")
os.environ.setdefault("DB_ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("APP_DATA_DIR", str(TEST_DATA_ROOT))
os.environ.setdefault("APP_CORS_ALLOWED_ORIGINS", "http://testserver,http://localhost:3000")
os.environ.setdefault("E2EE_PRIVATE_ENABLED", "1")
os.environ.setdefault("E2EE_GROUP_ENABLED", "1")


from app.chat.manager import manager as chat_manager
from app.database import SessionLocal, engine
from app.database.models import Base
from app.e2ee.service import ws_ticket_store
from app.settings import AVATAR_DIR, E2EE_ATTACHMENT_DIR, GROUP_AVATAR_DIR, LOG_FILE_PATH


def _reset_directory(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def _reset_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def reset_test_state():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ws_ticket_store._tickets.clear()
    chat_manager.active_connections.clear()

    _reset_directory(E2EE_ATTACHMENT_DIR)
    _reset_directory(AVATAR_DIR)
    _reset_directory(GROUP_AVATAR_DIR)
    _reset_file(LOG_FILE_PATH)
    yield


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
