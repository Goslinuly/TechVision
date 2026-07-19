"""OCR from photos (kaz+rus) — optional, off by default.

The MVP boundary (§1): text from images via Tesseract. Imported lazily so the
app runs without pytesseract / the system binary installed.
"""
from __future__ import annotations

from ..config import get_settings


def extract_text(image_bytes: bytes) -> str:
    settings = get_settings()
    if not settings.enable_ocr:
        return ""
    try:
        import io

        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    img = Image.open(io.BytesIO(image_bytes))
    # kaz+rus langpacks must be installed for tesseract.
    return pytesseract.image_to_string(img, lang="kaz+rus").strip()
