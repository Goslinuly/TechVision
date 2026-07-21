"""Embed the Factcheck.kz corpus with e5 and index it into pgvector (§3).

    EMBEDDINGS_ENABLED=true DATABASE_URL=postgres://... python -m scripts.index_corpus

Requires:
  pip install sentence-transformers "psycopg[binary]" pgvector

Reads data/factcheck_kz.json (build it first with scripts/build_corpus.py) or
the bundled sample, computes e5 passage embeddings, creates the schema, and
upserts. After this, local_corpus.search() uses pgvector automatically.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.services import embeddings, vectorstore

_DATA = Path(__file__).resolve().parents[1] / "data"


def _load_corpus() -> list[dict]:
    parsed = _DATA / "factcheck_kz.json"
    sample = _DATA / "factcheck_kz_sample.json"
    path = parsed if parsed.exists() else sample
    print(f"Loading corpus from {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if not embeddings.available():
        raise SystemExit(
            "embeddings unavailable — set EMBEDDINGS_ENABLED=true and "
            "`pip install sentence-transformers`"
        )
    if not vectorstore.available():
        raise SystemExit(
            "vectorstore unavailable — set DATABASE_URL and "
            "`pip install \"psycopg[binary]\" pgvector`"
        )

    corpus = _load_corpus()
    print(f"Embedding {len(corpus)} entries with e5…")
    vecs = embeddings.embed_passages([r["claim"] for r in corpus])

    vectorstore.ensure_schema(embeddings.dim())
    n = vectorstore.upsert(corpus, vecs)
    print(f"Indexed {n} entries into pgvector (dim={embeddings.dim()}).")


if __name__ == "__main__":
    main()
