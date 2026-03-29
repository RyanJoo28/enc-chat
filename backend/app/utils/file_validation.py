import os
from typing import Iterable


FILE_SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".pdf": (b"%PDF",),
    ".zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}

MIME_BY_EXTENSION = {
    ".png": {"image/png"},
    ".jpg": {"image/jpeg", "image/pjpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/pjpeg", "image/jpg"},
    ".gif": {"image/gif"},
    ".pdf": {"application/pdf"},
    ".zip": {"application/zip", "application/x-zip-compressed", "multipart/x-zip", "application/octet-stream"},
    ".txt": {"text/plain"},
}

TEXT_EXTENSIONS = {".txt"}


def _is_probably_utf8_text(content: bytes) -> bool:
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        return False

    if not decoded:
        return False

    printable_chars = sum(char.isprintable() or char in "\r\n\t" for char in decoded)
    return printable_chars / len(decoded) >= 0.95


def _matches_magic(ext: str, content: bytes) -> bool:
    if ext in TEXT_EXTENSIONS:
        return _is_probably_utf8_text(content)

    return any(content.startswith(signature) for signature in FILE_SIGNATURES.get(ext, ()))


def validate_file_payload(
        filename: str | None,
        content_type: str | None,
        content: bytes,
        allowed_extensions: Iterable[str]
) -> str:
    if not filename:
        raise ValueError("文件名无效")

    if not content:
        raise ValueError("文件为空")

    allowed = {item.lower() for item in allowed_extensions}
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed:
        raise ValueError("不支持的文件类型")

    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    allowed_mime_types = MIME_BY_EXTENSION.get(ext, set())
    if allowed_mime_types and normalized_content_type not in allowed_mime_types:
        raise ValueError("文件 MIME 类型不匹配")

    if not _matches_magic(ext, content):
        raise ValueError("文件内容与扩展名不匹配")

    return ext
