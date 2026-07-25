from app.services import image_forensics


def test_available_matches_pillow_presence():
    try:
        import PIL  # noqa: F401

        has_pil = True
    except ImportError:
        has_pil = False
    assert image_forensics.available() is has_pil


def test_analyze_never_raises_on_garbage():
    # Even on non-image bytes, analyze() must return a dict, not raise.
    out = image_forensics.analyze(b"not-an-image")
    assert isinstance(out, dict)
    assert "disclaimer" in out
    # Garbage → not a usable signal.
    if not image_forensics.available():
        assert out["available"] is False


def test_band_thresholds():
    assert image_forensics._band(0.1) == "low"
    assert image_forensics._band(0.5) == "medium"
    assert image_forensics._band(0.9) == "high"
