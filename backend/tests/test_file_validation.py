from app.utils.file_validation import validate_file_payload


PNG_BYTES = b"\x89PNG\r\n\x1a\nrest"
PDF_BYTES = b"%PDF-1.7\nrest"
TEXT_BYTES = "hello world".encode("utf-8")


def test_validate_file_payload_accepts_matching_png():
    ext = validate_file_payload("avatar.png", "image/png", PNG_BYTES, {".png"})

    assert ext == ".png"


def test_validate_file_payload_rejects_mime_mismatch():
    try:
        validate_file_payload("avatar.png", "image/jpeg", PNG_BYTES, {".png"})
    except ValueError as exc:
        assert str(exc) == "文件 MIME 类型不匹配"
    else:
        raise AssertionError("expected MIME mismatch to raise ValueError")


def test_validate_file_payload_rejects_magic_mismatch():
    try:
        validate_file_payload("report.pdf", "application/pdf", TEXT_BYTES, {".pdf"})
    except ValueError as exc:
        assert str(exc) == "文件内容与扩展名不匹配"
    else:
        raise AssertionError("expected magic mismatch to raise ValueError")


def test_validate_file_payload_accepts_utf8_text():
    ext = validate_file_payload("notes.txt", "text/plain", TEXT_BYTES, {".txt"})

    assert ext == ".txt"


def test_validate_file_payload_accepts_pdf_signature():
    ext = validate_file_payload("report.pdf", "application/pdf", PDF_BYTES, {".pdf"})

    assert ext == ".pdf"
