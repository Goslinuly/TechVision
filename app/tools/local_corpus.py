"""Semantic search over the Factcheck.kz corpus (§3, §5).

Three retrieval backends, chosen at runtime by what is configured/installed:

  1. pgvector  — e5 embeddings + cosine search in Postgres (prod);
  2. in-memory — e5 embeddings, cosine over the local JSON corpus;
  3. lexical   — dependency-free Jaccard fallback (default; runs without torch/DB).

All three return the same shape, so the orchestrator/tool contract is stable.
The similarity threshold τ depends on the scorer (cosine vs Jaccard).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from ..config import get_settings
from ..models import Evidence, Verdict
from ..services import embeddings, vectorstore

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
# Prefer the parsed corpus (scripts/build_corpus.py); fall back to the sample.
_CORPUS = _DATA_DIR / "factcheck_kz.json"
_SAMPLE = _DATA_DIR / "factcheck_kz_sample.json"

# τ for the lexical (Jaccard) fallback. Cosine τ lives in settings.tau_cosine.
TAU = 0.18

_VERDICT_MAP = {
    "refuted": Verdict.REFUTED,
    "supported": Verdict.SUPPORTED,
    "not_found": Verdict.NOT_FOUND,
}


@lru_cache
def _corpus() -> list[dict]:
    path = _CORPUS if _CORPUS.exists() else _SAMPLE
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def _corpus_embeddings() -> list[list[float]]:
    """e5 passage vectors for the in-memory cosine path (cached)."""
    return embeddings.embed_passages([r["claim"] for r in _corpus()])


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) > 2}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _retrieve(claim: str, top_k: int) -> tuple[list[tuple[float, dict]], float]:
    """Return ([(similarity, row)] desc, threshold) for the active backend."""
    if embeddings.available():
        qv = embeddings.embed_query(claim)
        tau = get_settings().tau_cosine
        if vectorstore.available():
            rows = vectorstore.search(qv, top_k)
            return [(float(r.pop("similarity")), r) for r in rows], tau
        corpus = _corpus()
        embs = _corpus_embeddings()
        ranked = sorted(
            ((embeddings.cosine(qv, e), row) for e, row in zip(embs, corpus)),
            key=lambda x: x[0],
            reverse=True,
        )
        return ranked[:top_k], tau

    ranked = sorted(
        ((_jaccard(claim, row["claim"]), row) for row in _corpus()),
        key=lambda x: x[0],
        reverse=True,
    )
    return ranked[:top_k], TAU


def search(claim: str, top_k: int = 3) -> dict:
    """Return the best corpus matches and an aggregate verdict signal.

    Result shape (also what the LLM tool sees):
      {"verdict": <str|None>, "matches": [{...evidence, similarity}]}
    """
    ranked, tau = _retrieve(claim, top_k)

    matches: list[Evidence] = []
    best_verdict: Verdict | None = None
    for sim, row in ranked:
        if sim < tau:
            continue
        matches.append(
            Evidence(
                source="Factcheck.kz",
                title=row.get("title", ""),
                url=row.get("url", ""),
                rating=row.get("rating", ""),
                similarity=round(float(sim), 3),
            )
        )
        if best_verdict is None:
            best_verdict = _VERDICT_MAP.get(row.get("verdict", ""), None)

    return {
        "verdict": best_verdict.value if best_verdict else None,
        "matches": [m.model_dump() for m in matches],
    }
