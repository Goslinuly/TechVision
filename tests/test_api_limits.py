"""Security: the /analyze endpoint must cap untrusted input length (§)."""
from starlette.testclient import TestClient

from app.main import MAX_INPUT_CHARS, app


def test_analyze_rejects_empty_text():
    with TestClient(app) as client:
        r = client.post("/analyze", json={"text": "   "})
    assert r.status_code == 400


def test_analyze_truncates_oversized_input():
    # Oversized forwarded text is truncated, never let through whole: the stored
    # source_text must not exceed the server-side cap.
    with TestClient(app) as client:
        r = client.post("/analyze", json={"text": "спам " * 2000})
    assert r.status_code == 200
    card = r.json()["card"]
    assert len(card["source_text"]) <= MAX_INPUT_CHARS


def test_analyze_normal_input_unchanged():
    text = "Средняя зарплата превысила 400 тысяч тенге"
    with TestClient(app) as client:
        r = client.post("/analyze", json={"text": text})
    assert r.status_code == 200
    assert r.json()["card"]["source_text"] == text
