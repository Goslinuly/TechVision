"""multilingual-e5 embeddings (§3) — optional, heavy dependency.

Replaces the lexical placeholder in local_corpus with real semantic vectors.
Gated behind EMBEDDINGS_ENABLED + a present `sentence-transformers` install, so
the app still runs (and tests pass) without torch. e5 requires the "query:" /
"passage:" prefixes — encoded here so callers don't have to remember.

    pip install sentence-transformers        # then EMBEDDINGS_ENABLED=true
"""
from __future__ import annotations

from functools import lru_cache

from ..config import get_settings

_model = None


def available() -> bool:
    if not get_settings().embeddings_enabled:
        return False
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(get_settings().embeddings_model)
    return _model


def embed_query(text: str) -> list[float]:
    v = _get_model().encode("query: " + text, normalize_embeddings=True)
    return v.tolist()


def embed_passages(texts: list[str]) -> list[list[float]]:
    vs = _get_model().encode(
        ["passage: " + t for t in texts], normalize_embeddings=True
    )
    return [v.tolist() for v in vs]


def cosine(a: list[float], b: list[float]) -> float:
    """Vectors are L2-normalized, so cosine == dot product."""
    return sum(x * y for x, y in zip(a, b))


@lru_cache
def dim() -> int:
    return _get_model().get_sentence_embedding_dimension()
