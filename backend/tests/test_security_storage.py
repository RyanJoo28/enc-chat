from hashlib import sha256
from datetime import datetime, timedelta

from sqlalchemy import text

from app.database import SessionLocal
from app.database.__init__ import _hash_legacy_token_blacklist
from app.database.models import (
    AuthSession,
    Device,
    DeviceSignedPrekey,
    GroupJoinRequest,
    MessagePayload,
    MessageV2,
    User,
)
from app.utils import encryption


# ─────────────────────────────────────────────────────────
# 1. token_blacklist SHA-256 hashing
# ─────────────────────────────────────────────────────────

def test_token_blacklist_stores_hash_not_plaintext(db_session):
    """logout 时存储 SHA-256(token)，而非明文 JWT。"""
    raw_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.signature"
    token_hash = sha256(raw_token.encode()).hexdigest()

    db_session.execute(
        text("INSERT INTO token_blacklist (token) VALUES (:tok)"),
        {"tok": token_hash},
    )
    db_session.commit()

    # 列中只存哈希，不含明文 token
    row = db_session.execute(text("SELECT token FROM token_blacklist")).fetchone()
    assert row is not None
    assert len(row[0]) == 64  # SHA-256 hex
    assert raw_token not in row[0]


def test_token_blacklist_legacy_migration_hashes_plaintext(db_session):
    """启动迁移将明文 JWT 替换为 SHA-256 哈希。"""
    raw_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJvbGQifQ.old_sig"
    expected_hash = sha256(raw_token.encode()).hexdigest()

    # 模拟旧版明文存储
    db_session.execute(
        text("INSERT INTO token_blacklist (token) VALUES (:tok)"),
        {"tok": raw_token},
    )
    db_session.commit()

    # 执行启动迁移
    _hash_legacy_token_blacklist()

    row = db_session.execute(text("SELECT token FROM token_blacklist")).fetchone()
    assert row is not None
    assert row[0] == expected_hash


def test_token_blacklist_migration_idempotent_on_already_hashed(db_session):
    """已存哈希的条目不会被二次哈希。"""
    token_hash = sha256(b"already_hashed").hexdigest()
    db_session.execute(
        text("INSERT INTO token_blacklist (token) VALUES (:tok)"),
        {"tok": token_hash},
    )
    db_session.commit()

    _hash_legacy_token_blacklist()

    row = db_session.execute(text("SELECT token FROM token_blacklist")).fetchone()
    assert row[0] == token_hash


# ─────────────────────────────────────────────────────────
# 2. auth_sessions.ip_address 加密
# ─────────────────────────────────────────────────────────

def test_ip_address_encrypted_at_rest(db_session):
    """ip_address 列明文不可见，property 自动加解密。"""
    ref_user = _ref_user(db_session)

    session = AuthSession(
        session_id="test-sid",
        user_id=ref_user.id,
        refresh_token_hash="rk",
        session_family_id="sf-1",
        user_session_version=1,
        status="active",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    session.ip_address = "192.168.1.100"
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    sid = session.id

    # 通过 property 读取明文
    session2 = db_session.get(AuthSession, sid)
    assert session2.ip_address == "192.168.1.100"

    # 直接查原始列，不应出现明文 IP
    row = db_session.execute(
        text("SELECT ip_address FROM auth_sessions WHERE id = :sid"), {"sid": sid}
    ).fetchone()
    raw_col = row[0]
    assert "192.168.1.100" not in raw_col
    # 加密格式：base64(IV)|base64(ciphertext)
    assert "|" in raw_col


def test_ip_address_none_does_not_encrypt(db_session):
    """ip_address=None 不加密封装。"""
    ref_user = _ref_user(db_session)
    session = AuthSession(
        session_id="sid-none",
        user_id=ref_user.id,
        refresh_token_hash="rk2",
        session_family_id="sf-2",
        user_session_version=1,
        status="active",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    session.ip_address = None
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    row = db_session.execute(
        text("SELECT ip_address FROM auth_sessions WHERE id = :sid"), {"sid": session.id}
    ).fetchone()
    assert row[0] is None


# ─────────────────────────────────────────────────────────
# 3. group_join_requests.note 加密
# ─────────────────────────────────────────────────────────

def test_group_join_request_note_encrypted(db_session):
    """入群申请的 note 字段加密存储。"""
    ref_user = _ref_user(db_session)
    join_req = GroupJoinRequest(
        group_id=1,
        requester_id=ref_user.id,
        status="pending",
    )
    join_req.note = "请让我入群，我是朋友"
    db_session.add(join_req)
    db_session.commit()
    db_session.refresh(join_req)

    # property 返回明文
    assert join_req.note == "请让我入群，我是朋友"

    # 原始列不含明文
    row = db_session.execute(
        text("SELECT note FROM group_join_requests WHERE id = :rid"), {"rid": join_req.id}
    ).fetchone()
    assert "请让我入群" not in row[0]
    assert "|" in row[0]


def test_group_join_request_note_none_passthrough(db_session):
    """note=None 不加密。"""
    ref_user = _ref_user(db_session)
    join_req = GroupJoinRequest(group_id=1, requester_id=ref_user.id, status="pending")
    join_req.note = None
    db_session.add(join_req)
    db_session.commit()
    db_session.refresh(join_req)

    row = db_session.execute(
        text("SELECT note FROM group_join_requests WHERE id = :rid"), {"rid": join_req.id}
    ).fetchone()
    assert row[0] is None


# ─────────────────────────────────────────────────────────
# 4. MessagePayload.envelope 防御性加密
# ─────────────────────────────────────────────────────────

def test_envelope_encrypted_at_rest(db_session):
    """envelope 列在 DB 中经过 db_encrypt 包裹，原始密文不可见。"""
    ref_user = _ref_user(db_session)
    user2 = _ref_user2(db_session)

    # Create a conversation_v2 row properly
    conv_low = min(ref_user.id, user2.id)
    conv_high = max(ref_user.id, user2.id)
    db_session.execute(
        text(
            "INSERT INTO conversations_v2 (conversation_key, conversation_type, pair_user_low_id, pair_user_high_id) "
            "VALUES (:key, 'private', :low, :high)"
        ),
        {"key": f"e2ee:{conv_low}:{conv_high}", "low": conv_low, "high": conv_high},
    )
    conv_id = db_session.execute(text("SELECT last_insert_rowid()")).scalar()
    msg = MessageV2(
        conversation_id=conv_id,
        sender_user_id=ref_user.id,
        client_message_id="cm1",
        protocol_version="e2ee_v1",
        message_type="text",
    )
    db_session.add(msg)
    db_session.flush()

    payload = MessagePayload(
        message_id=msg.id,
        recipient_user_id=ref_user.id,
        recipient_device_id=1,
        envelope_type="signal",
        protocol_version="e2ee_v1",
    )
    raw_envelope = '{"ciphertext":"encrypted-base64","nonce":"abc"}'
    payload.envelope = raw_envelope
    db_session.add(payload)
    db_session.commit()
    db_session.refresh(payload)

    # property 返回原始明文
    assert payload.envelope == raw_envelope

    # DB 原始列不含 E2EE 密文
    row = db_session.execute(
        text("SELECT envelope FROM message_payloads WHERE id = :pid"), {"pid": payload.id}
    ).fetchone()
    assert "encrypted-base64" not in row[0]
    assert "|" in row[0]


# ─────────────────────────────────────────────────────────
# 5. users.password 外层 AES 加密
# ─────────────────────────────────────────────────────────

def test_password_encrypted_at_rest(db_session):
    """Argon2 hash 外层被 db_encrypt 包裹，DB 列不含 Argon2 特征串。"""
    argon_hash = "$argon2id$v=19$m=65536,t=3,p=4$abc123$def456"
    user = User(e2ee_enabled=True)
    user.username = "pwtest"
    user.password = argon_hash
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.password == argon_hash

    row = db_session.execute(
        text("SELECT password FROM users WHERE id = :uid"), {"uid": user.id}
    ).fetchone()
    assert "$argon2id" not in row[0]
    assert "|" in row[0]


# ─────────────────────────────────────────────────────────
# 6. 文件加密 HMAC 认证
# ─────────────────────────────────────────────────────────

def test_encrypt_file_content_includes_hmac_tag():
    """encrypt 返回 MAGIC+IV+ciphertext+HMAC(32 bytes)。"""
    plaintext = b"secret file content"
    enc = encryption.encrypt_file_content(plaintext)
    magic = encryption.FILE_ENCRYPTION_MAGIC
    assert enc.startswith(magic)
    payload = enc[len(magic):]
    assert len(payload) >= 16 + 16 + encryption.HMAC_SIZE  # IV + ciphertext(min 16 padded) + HMAC


def test_file_encryption_roundtrip(db_session):
    """正常加密→解密可还原。"""
    plaintext = b"hello world secure file"
    enc = encryption.encrypt_file_content(plaintext)
    dec = encryption.decrypt_file_content(enc)
    assert dec == plaintext


def test_tampered_hmac_rejected():
    """篡改 HMAC 标签后解密失败。"""
    plaintext = b"sensitive data"
    enc = encryption.encrypt_file_content(plaintext)
    # 翻转最后一个字节（HMAC 标签内）
    tampered = bytearray(enc)
    tampered[-1] ^= 0xFF
    result = encryption.decrypt_file_content(bytes(tampered))
    assert result == b""


def test_legacy_no_hmac_file_still_decryptable():
    """旧版无 HMAC 文件仍可解密（向后兼容）。"""
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    from Crypto.Util.Padding import pad

    plaintext = b"legacy file"
    iv = get_random_bytes(16)
    cipher = AES.new(encryption.DB_SECRET_KEY, AES.MODE_CBC, iv)
    legacy = encryption.FILE_ENCRYPTION_MAGIC + iv + cipher.encrypt(pad(plaintext, 16))
    # 旧版格式不含 HMAC 尾巴
    dec = encryption.decrypt_file_content(legacy)
    assert dec == plaintext


def test_plaintext_fallback_disabled_rejects_plaintext():
    """allow_plaintext_fallback=False 时明文文件返回空。"""
    result = encryption.decrypt_file_content(b"i am plaintext", allow_plaintext_fallback=False)
    assert result == b""


def test_plaintext_fallback_enabled_returns_as_is():
    """allow_plaintext_fallback=True 时明文原样返回。"""
    result = encryption.decrypt_file_content(b"raw content", allow_plaintext_fallback=True)
    assert result == b"raw content"


# ─────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────

def _ref_user(db_session) -> User:
    user = User(e2ee_enabled=True)
    user.username = "security_test_user"
    user.password = "$argon2id$placeholder$test$pw"
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _ref_user2(db_session) -> User:
    user = User(e2ee_enabled=True)
    user.username = "security_test_user2"
    user.password = "$argon2id$placeholder$test2$pw"
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
