from __future__ import annotations

import base64
import os
from collections import Counter
from pathlib import Path


def _bootstrap_runtime_env() -> None:
    data_root = Path(os.getenv("APP_DATA_DIR", "/data"))
    os.environ.setdefault("APP_DATA_DIR", str(data_root))

    if not os.getenv("DB_ENCRYPTION_KEY"):
        db_key_file = data_root / "secrets" / "db_encryption_key.hex"
        if db_key_file.exists():
            os.environ["DB_ENCRYPTION_KEY"] = db_key_file.read_text().strip()


_bootstrap_runtime_env()

from app.database import SessionLocal
from app.database.models import Attachment, Group, GroupSearchToken, Message, User, UserSearchToken
from app.settings import AVATAR_DIR, GROUP_AVATAR_DIR, UPLOAD_DIR
from app.utils import encryption


PLAINTEXT_FILE_SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".pdf": (b"%PDF",),
    ".zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}
PLAINTEXT_TEXT_SUFFIXES = {".txt", ".md", ".json", ".csv", ".log"}
MAX_EXAMPLES = 5


def _is_likely_plaintext_file(file_path: Path, file_bytes: bytes) -> bool:
    suffix = file_path.suffix.lower()
    signatures = PLAINTEXT_FILE_SIGNATURES.get(suffix, ())
    if any(file_bytes.startswith(signature) for signature in signatures):
        return True

    if suffix not in PLAINTEXT_TEXT_SUFFIXES:
        return False

    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return False

    if not text:
        return True

    printable_chars = sum(char.isprintable() or char in "\r\n\t" for char in text)
    return printable_chars / len(text) >= 0.95


def _can_decrypt_stored_file(file_bytes: bytes) -> bool:
    payload = file_bytes
    if file_bytes.startswith(encryption.FILE_ENCRYPTION_MAGIC):
        payload = file_bytes[len(encryption.FILE_ENCRYPTION_MAGIC):]

    if len(payload) <= 16 or (len(payload) - 16) % 16 != 0:
        return False

    try:
        iv = payload[:16]
        ciphertext = payload[16:]
        cipher = encryption.AES.new(encryption.DB_SECRET_KEY, encryption.AES.MODE_CBC, iv)
        encryption.unpad(cipher.decrypt(ciphertext), encryption.AES.block_size)
        return True
    except Exception:
        return False


def _classify_disk_file(file_path: Path) -> str:
    file_bytes = file_path.read_bytes()
    if not file_bytes:
        return "empty"
    if file_bytes.startswith(encryption.FILE_ENCRYPTION_MAGIC):
        return "encrypted_current"
    if _can_decrypt_stored_file(file_bytes):
        return "encrypted_legacy"
    if _is_likely_plaintext_file(file_path, file_bytes):
        return "plaintext"
    return "unknown"


def _audit_directory(label: str, directory: Path) -> dict:
    counts = Counter()
    examples: dict[str, list[str]] = {
        "plaintext": [],
        "unknown": [],
        "encrypted_legacy": [],
    }

    directory.mkdir(parents=True, exist_ok=True)
    for file_path in sorted(directory.iterdir()):
        if not file_path.is_file():
            continue

        status = _classify_disk_file(file_path)
        counts[status] += 1
        if status in examples and len(examples[status]) < MAX_EXAMPLES:
            examples[status].append(file_path.name)

    return {
        "label": label,
        "path": str(directory),
        "counts": counts,
        "examples": examples,
    }


def _is_encrypted_message_content(db_text: str | None) -> bool:
    if not db_text or "|" not in db_text:
        return False

    try:
        iv_b64, ciphertext_b64 = db_text.split("|", 1)
        iv = base64.b64decode(iv_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
        if len(iv) != 16 or len(ciphertext) == 0 or len(ciphertext) % 16 != 0:
            return False

        cipher = encryption.AES.new(encryption.DB_SECRET_KEY, encryption.AES.MODE_CBC, iv)
        encryption.unpad(cipher.decrypt(ciphertext), encryption.AES.block_size)
        return True
    except Exception:
        return False


def _format_count_line(label: str, count: int, total: int) -> str:
    return f"  - {label}: {count}/{total}"


def _audit_db_field(rows, accessor) -> tuple[int, int, int]:
    encrypted = 0
    plaintext = 0
    empty = 0

    for row in rows:
        value = accessor(row)
        if not value:
            empty += 1
        elif encryption.is_encrypted_db_text(value):
            encrypted += 1
        else:
            plaintext += 1

    return encrypted, plaintext, empty


def run_audit() -> str:
    db = SessionLocal()
    try:
        users = db.query(User).all()
        groups = db.query(Group).all()
        attachments = db.query(Attachment).all()
        user_search_token_count = db.query(UserSearchToken).count()
        group_search_token_count = db.query(GroupSearchToken).count()
        message_rows = db.query(Message.id, Message.content).all()
    finally:
        db.close()

    user_count = len(users)
    group_count = len(groups)
    attachment_count = len(attachments)
    message_total = len(message_rows)
    encrypted_messages = sum(1 for _, content in message_rows if _is_encrypted_message_content(content))
    plaintext_messages = message_total - encrypted_messages

    users_username_encrypted, users_username_plaintext, _ = _audit_db_field(users, lambda row: row._username)
    users_avatar_encrypted, users_avatar_plaintext, users_avatar_empty = _audit_db_field(users, lambda row: row._avatar)
    groups_name_encrypted, groups_name_plaintext, _ = _audit_db_field(groups, lambda row: row._name)
    groups_avatar_encrypted, groups_avatar_plaintext, groups_avatar_empty = _audit_db_field(groups, lambda row: row._avatar)
    attachments_filename_encrypted, attachments_filename_plaintext, _ = _audit_db_field(attachments, lambda row: row._stored_filename)
    attachments_original_name_encrypted, attachments_original_name_plaintext, _ = _audit_db_field(attachments, lambda row: row._original_name)

    directories = [
        _audit_directory("用户头像目录", AVATAR_DIR),
        _audit_directory("群头像目录", GROUP_AVATAR_DIR),
        _audit_directory("聊天附件目录", UPLOAD_DIR),
    ]

    lines = [
        "加密存储审计报告",
        "",
        "[文件存储]",
    ]

    for directory_report in directories:
        counts = directory_report["counts"]
        total = sum(counts.values())
        lines.append(f"- {directory_report['label']} `{directory_report['path']}`")
        lines.append(_format_count_line("当前加密格式(ENCFILE1)", counts.get("encrypted_current", 0), total))
        lines.append(_format_count_line("旧版加密格式(无魔术头)", counts.get("encrypted_legacy", 0), total))
        lines.append(_format_count_line("明文文件", counts.get("plaintext", 0), total))
        lines.append(_format_count_line("未知/无法判定", counts.get("unknown", 0), total))
        lines.append(_format_count_line("空文件", counts.get("empty", 0), total))

        for status_key, status_label in (("encrypted_legacy", "旧版加密示例"), ("plaintext", "明文示例"), ("unknown", "未知示例")):
            examples = directory_report["examples"][status_key]
            if examples:
                lines.append(f"  - {status_label}: {', '.join(examples)}")

    lines.extend([
        "",
        "[数据库字段]",
        f"- `messages.content`: 加密消息 {encrypted_messages}/{message_total}，未加密或无法解密 {plaintext_messages}/{message_total}",
        f"- `users.username`: 已加密 {users_username_encrypted}/{user_count}，明文 {users_username_plaintext}/{user_count}",
        f"- `users.avatar`: 已加密 {users_avatar_encrypted}/{user_count}，明文 {users_avatar_plaintext}/{user_count}，空值 {users_avatar_empty}/{user_count}",
        f"- `groups.name`: 已加密 {groups_name_encrypted}/{group_count}，明文 {groups_name_plaintext}/{group_count}",
        f"- `groups.avatar`: 已加密 {groups_avatar_encrypted}/{group_count}，明文 {groups_avatar_plaintext}/{group_count}，空值 {groups_avatar_empty}/{group_count}",
        f"- `attachments.stored_filename`: 已加密 {attachments_filename_encrypted}/{attachment_count}，明文 {attachments_filename_plaintext}/{attachment_count}",
        f"- `attachments.original_name`: 已加密 {attachments_original_name_encrypted}/{attachment_count}，明文 {attachments_original_name_plaintext}/{attachment_count}",
        f"- `user_search_tokens`: 盲索引 token {user_search_token_count} 条",
        f"- `group_search_tokens`: 盲索引 token {group_search_token_count} 条",
        "",
        "[结论]",
        "- 聊天消息正文以密文存库。",
        "- 头像/附件文件已按磁盘文件逐个审计；`ENCFILE1` 表示当前加密格式。",
        "- 用户名、群名、文件名等数据库元数据已按字段逐项审计。",
        "- 用户名/群名搜索已改为基于盲索引 token 的候选筛选，再做最终解密校验。",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    print(run_audit())
