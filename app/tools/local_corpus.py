"""Local semantic search over the Factcheck.kz corpus.

Production (§3): multilingual-e5 embeddings + pgvector on Supabase, cosine
similarity with a threshold τ. For the MVP skeleton we ship a dependency-free
lexical scorer (token-overlap / Jaccard) so the pipeline runs without torch or
a database. The public `search()` signature and the returned shape are the same
either way — swapping in real embeddings is a drop-in change of `_score()`.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from ..models import Evidence, Verdict

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
# Prefer the parsed corpus (scripts/build_corpus.py); fall back to the sample.
_CORPUS = _DATA_DIR / "factcheck_kz.json"
_SAMPLE = _DATA_DIR / "factcheck_kz_sample.json"

# τ — similarity threshold above which we treat the corpus hit as a match (§5).
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


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) > 2}


def _score(a: str, b: str) -> float:
    """Placeholder for cosine(e5(a), e5(b)). Jaccard over content tokens."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def search(claim: str, top_k: int = 3) -> dict:
    """Return the best corpus matches and an aggregate verdict signal.

    Result shape (also what the LLM tool sees):
      {"verdict": <str|None>, "matches": [{...evidence, similarity}]}
    """
    ranked = sorted(
        ((_score(claim, row["claim"]), row) for row in _corpus()),
        key=lambda x: x[0],
        reverse=True,
    )
    matches: list[Evidence] = []
    best_verdict: Verdict | None = None
    for sim, row in ranked[:top_k]:
        if sim < TAU:
            continue
        matches.append(
            Evidence(
                source="Factcheck.kz",
                title=row.get("title", ""),
                url=row.get("url", ""),
                rating=row.get("rating", ""),
                similarity=round(sim, 3),
            )
        )
        if best_verdict is None:
            best_verdict = _VERDICT_MAP.get(row.get("verdict", ""), None)

    return {
        "verdict": best_verdict.value if best_verdict else None,
        "matches": [m.model_dump() for m in matches],
    }
