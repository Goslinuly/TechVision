from app.services import ocr


def test_ocr_disabled_returns_empty(monkeypatch):
    from app import config

    monkeypatch.setattr(config.get_settings(), "enable_ocr", False, raising=False)
    # Even with bytes, disabled OCR returns "" and never imports/raises.
    assert ocr.extract_text(b"\x89PNG fake") == ""


def test_ocr_enabled_without_tesseract_is_graceful(monkeypatch):
    from app import config

    monkeypatch.setattr(config.get_settings(), "enable_ocr", True, raising=False)
    # If pytesseract / Pillow (or the system binary) are missing, we must
    # degrade to "" rather than crash the request path.
    try:
        result = ocr.extract_text(b"not-a-real-image")
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"OCR path raised instead of degrading: {exc}")
    assert isinstance(result, str)
