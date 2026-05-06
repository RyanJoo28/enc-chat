import base64
import hashlib
import hmac
import logging
import os
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from dotenv import load_dotenv

from .log_utils import build_log_payload, log_event

FILE_ENCRYPTION_MAGIC = b"ENCFILE1"
HMAC_SIZE = 32  # bytes
DB_DECRYPTION_FAILED_PLACEHOLDER = "[解密失败]"
PLAINTEXT_FILE_SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".pdf": (b"%PDF",),
    ".zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}
PLAINTEXT_TEXT_SUFFIXES = {".txt", ".md", ".json", ".csv", ".log"}
logger = logging.getLogger(__name__)


# 数据库存储加密密钥
load_dotenv()

_db_key_hex = os.getenv("DB_ENCRYPTION_KEY")

if not _db_key_hex:
    raise ValueError("严重错误: 未设置 DB_ENCRYPTION_KEY 环境变量！")

try:
    DB_SECRET_KEY = bytes.fromhex(_db_key_hex)
except ValueError:
    raise ValueError("DB_ENCRYPTION_KEY 格式错误，必须是有效的 Hex 字符串")

if len(DB_SECRET_KEY) != 32:
    raise ValueError("DB_ENCRYPTION_KEY 长度错误，解码后必须是 32 字节 (即 .env 中要有 64 个字符)")

# 文件加密的 HMAC 密钥（通过 domain separation 派生，避免与 DB 密钥直接共用）
_DB_FILE_HMAC_KEY = hmac.digest(DB_SECRET_KEY, b"enc-chat:file-hmac", "sha256")


def db_encrypt(plaintext: str) -> str:
    """加密文本数据以便存入数据库。"""
    try:
        iv = get_random_bytes(16)
        cipher = AES.new(DB_SECRET_KEY, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(pad(plaintext.encode('utf-8'), AES.block_size))

        iv_b64 = base64.b64encode(iv).decode('utf-8')
        ct_b64 = base64.b64encode(ciphertext).decode('utf-8')

        return f"{iv_b64}|{ct_b64}"
    except Exception as exc:
        logger.exception(build_log_payload("db_encrypt_failed", error=str(exc)))
        raise RuntimeError("数据库加密失败") from exc


def db_decrypt(db_text: str) -> str:
    """从数据库中读取并解密文本。"""
    try:
        if "|" not in db_text:
            return db_text

        iv_b64, ct_b64 = db_text.split("|")
        iv = base64.b64decode(iv_b64)
        ciphertext = base64.b64decode(ct_b64)

        cipher = AES.new(DB_SECRET_KEY, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return plaintext.decode('utf-8')
    except Exception as exc:
        log_event(logger, logging.WARNING, "db_decrypt_failed", error=str(exc))
        return DB_DECRYPTION_FAILED_PLACEHOLDER


def is_encrypted_db_text(db_text: str | None) -> bool:
    """判断数据库字符串字段是否采用当前 iv|ciphertext 格式。"""
    if not db_text or "|" not in db_text:
        return False

    try:
        iv_b64, ct_b64 = db_text.split("|", 1)
        iv = base64.b64decode(iv_b64)
        ciphertext = base64.b64decode(ct_b64)
        return len(iv) == 16 and len(ciphertext) > 0 and len(ciphertext) % 16 == 0
    except Exception:
        return False


def normalize_search_text(text: str) -> str:
    """归一化文本，便于做大小写不敏感的搜索与排序。"""
    return " ".join(text.strip().casefold().split())


def metadata_hash(value: str, case_insensitive: bool = False, namespace: str = "metadata") -> str:
    """为可检索元数据生成稳定哈希。"""
    normalized = value.casefold() if case_insensitive else value
    payload = f"{namespace}\0{normalized}".encode("utf-8")
    return hmac.new(DB_SECRET_KEY, payload, hashlib.sha256).hexdigest()


def build_blind_index_tokens(value: str, max_token_length: int = 3) -> list[str]:
    """为模糊搜索生成去重后的 n-gram 盲索引 token。"""
    normalized = normalize_search_text(value)
    if not normalized:
        return []

    token_length = min(max_token_length, len(normalized))
    tokens = set()
    for size in range(1, token_length + 1):
        for index in range(len(normalized) - size + 1):
            tokens.add(normalized[index:index + size])

    return sorted(tokens)


def build_blind_index_hashes(value: str, namespace: str, max_token_length: int = 3) -> list[str]:
    """为模糊搜索生成加盐哈希 token 列表。"""
    return [metadata_hash(token, namespace=namespace) for token in build_blind_index_tokens(value, max_token_length=max_token_length)]


def encrypt_file_content(file_bytes: bytes) -> bytes:
    """加密二进制文件内容（AES-256-CBC + HMAC-SHA256 认证）。"""
    iv = get_random_bytes(16)
    cipher = AES.new(DB_SECRET_KEY, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(file_bytes, AES.block_size))
    body = iv + ciphertext
    tag = hmac.digest(_DB_FILE_HMAC_KEY, FILE_ENCRYPTION_MAGIC + body, "sha256")
    return FILE_ENCRYPTION_MAGIC + body + tag


def decrypt_file_content(encrypted_bytes: bytes, allow_plaintext_fallback: bool = False) -> bytes:
    """解密二进制文件内容，验证 HMAC。兼容旧版无 HMAC 格式。"""
    payload = encrypted_bytes
    if encrypted_bytes.startswith(FILE_ENCRYPTION_MAGIC):
        payload = encrypted_bytes[len(FILE_ENCRYPTION_MAGIC):]
    elif allow_plaintext_fallback:
        return encrypted_bytes

    try:
        has_hmac = len(payload) > 16 + HMAC_SIZE
        if has_hmac:
            signed_body = payload[:-HMAC_SIZE]
            expected_tag = payload[-HMAC_SIZE:]
            actual_tag = hmac.digest(_DB_FILE_HMAC_KEY, FILE_ENCRYPTION_MAGIC + signed_body, "sha256")
            if not hmac.compare_digest(actual_tag, expected_tag):
                raise ValueError("File HMAC verification failed")
            body = signed_body
        else:
            body = payload

        if len(body) <= 16:
            raise ValueError("Encrypted payload is too short")

        iv = body[:16]
        ciphertext = body[16:]
        cipher = AES.new(DB_SECRET_KEY, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return plaintext
    except Exception as exc:
        log_event(logger, logging.WARNING, "file_decrypt_failed", error=str(exc))
        if allow_plaintext_fallback:
            return encrypted_bytes
        return b""


def is_encrypted_file_content(file_bytes: bytes) -> bool:
    """判断文件是否采用当前带魔术头的加密格式。"""
    return file_bytes.startswith(FILE_ENCRYPTION_MAGIC)


def is_plaintext_image_file(file_path: Path, file_bytes: bytes) -> bool:
    """根据扩展名和文件头判断是否还是明文图片。"""
    signatures = PLAINTEXT_FILE_SIGNATURES.get(file_path.suffix.lower(), ())
    return any(file_bytes.startswith(signature) for signature in signatures)


def is_likely_plaintext_file(file_path: Path, file_bytes: bytes) -> bool:
    """根据扩展名和内容判断是否是明文文件。"""
    signatures = PLAINTEXT_FILE_SIGNATURES.get(file_path.suffix.lower(), ())
    if any(file_bytes.startswith(signature) for signature in signatures):
        return True

    if file_path.suffix.lower() not in PLAINTEXT_TEXT_SUFFIXES:
        return False

    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return False

    if not text:
        return True

    printable_chars = sum(char.isprintable() or char in "\r\n\t" for char in text)
    return printable_chars / len(text) >= 0.95


def migrate_plaintext_file_to_encrypted_storage(file_path: Path) -> bool:
    """将旧的明文图片文件原地迁移为加密存储。"""
    if not file_path.is_file():
        return False

    raw_bytes = file_path.read_bytes()
    if not raw_bytes or is_encrypted_file_content(raw_bytes):
        return False

    if not is_plaintext_image_file(file_path, raw_bytes):
        return False

    temp_path = file_path.with_name(f".{file_path.name}.migrating")
    try:
        temp_path.write_bytes(encrypt_file_content(raw_bytes))
        temp_path.replace(file_path)
        return True
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def migrate_plaintext_files_in_directory(directory: Path) -> tuple[int, int]:
    """批量迁移目录中的旧明文图片文件。"""
    directory.mkdir(parents=True, exist_ok=True)
    scanned_count = 0
    migrated_count = 0

    for file_path in directory.iterdir():
        if not file_path.is_file():
            continue

        scanned_count += 1
        try:
            if migrate_plaintext_file_to_encrypted_storage(file_path):
                migrated_count += 1
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "plaintext_file_migration_failed",
                filename=file_path.name,
                error=str(exc),
            )

    return scanned_count, migrated_count

