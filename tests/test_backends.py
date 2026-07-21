"""Availability gating + fallbacks for the optional backends (e5, pgvector,
KazLLM). None are configured in the test env, so each must report unavailable
and the pipeline must fall back cleanly."""
from app.services import embeddings, kazllm, vectorstore
from app.tools import local_corpus
from app.orchestrator.tools import kazllm_specialist


def test_embeddings_unavailable_by_default():
    # EMBEDDINGS_ENABLED defaults false → lexical path.
    assert embeddings.available() is False


def test_vectorstore_unavailable_without_database_url():
    assert vectorstore.available() is False


def test_kazllm_unavailable_without_base_url():
    assert kazllm.available() is False


def test_kazllm_specialist_falls_back_to_stub():
    out = kazllm_specialist("Аңдағайдай сөз")
    assert out["available"] is False
    assert "stub" in out["note"].lower()


def test_local_corpus_uses_lexical_fallback(monkeypatch):
    from pathlib import Path

    monkeypatch.setattr(local_corpus, "_CORPUS", Path("/nonexistent/none.json"))
    local_corpus._corpus.cache_clear()
    out = local_corpus.search("вакцина вызвала 5000 смертей в Алматы")
    local_corpus._corpus.cache_clear()
    assert out["verdict"] == "refuted"  # lexical match still works
