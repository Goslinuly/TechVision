"""Image-manipulation *signal* — §1 / §5 «второстепенный сигнал».

Deliberately NOT a deepfake verdict. Open detectors sit around ~78% AUC, so a
confident «fake/real» call would contradict Aqıqat's whole premise. Instead we
return an explainable, honest *signal*:

  * ELA (Error Level Analysis) — recompress as JPEG and measure the residual
    error; edited/pasted regions tend to show a different error level;
  * metadata / EXIF hints — editing-software or AI-generator tags.

The result carries an explicit disclaimer and a suspicion band, never a verdict.
Optional dependency (Pillow); degrades to `available: False` without it.
Use only on the team's own demo material (as the TZ states aloud).
"""
from __future__ import annotations

import io

_DISCLAIMER = (
    "Второстепенный сигнал, не вердикт. Открытые детекторы дипфейков дают лишь "
    "~78% AUC, поэтому мы показываем подозрительность, а не «фейк/подлинник». "
    "Использовать только на собственном демо-материале."
)

_EDIT_TAGS = ("photoshop", "gimp", "lightroom", "snapseed", "pixelmator", "paint")
_AI_TAGS = ("stable diffusion", "midjourney", "dall", "generated", "gan", "firefly")


def available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def _band(score: float) -> str:
    return "high" if score >= 0.66 else "medium" if score >= 0.33 else "low"


def analyze(image_bytes: bytes) -> dict:
    """Return an image-manipulation signal (never raises)."""
    try:
        from PIL import Image, ImageChops, ImageStat

        src = Image.open(io.BytesIO(image_bytes))
        exif = src.getexif()
        software = (exif.get(0x0131) or "") if exif else ""
        sw_low = str(software).lower()

        # ELA: recompress and measure residual error.
        rgb = src.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, "JPEG", quality=90)
        buf.seek(0)
        recompressed = Image.open(buf)
        diff = ImageChops.difference(rgb, recompressed)
        stat = ImageStat.Stat(diff)
        mean_err = sum(stat.mean) / len(stat.mean)
        # Heuristic normalization: authentic re-saves sit low (~1–3).
        ela_score = round(min(1.0, mean_err / 12.0), 3)

        return {
            "available": True,
            "kind": "secondary_signal",
            "ela_score": ela_score,
            "suspicion": _band(ela_score),
            "metadata": {
                "has_exif": bool(exif),
                "editing_software": software or None,
                "editing_hint": any(t in sw_low for t in _EDIT_TAGS),
                "ai_generator_hint": any(t in sw_low for t in _AI_TAGS),
            },
            "disclaimer": _DISCLAIMER,
        }
    except Exception as exc:  # noqa: BLE001 — never break the caller
        return {"available": False, "error": str(exc), "disclaimer": _DISCLAIMER}
