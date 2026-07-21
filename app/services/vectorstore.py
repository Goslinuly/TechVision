"""pgvector on Supabase/Postgres (§3) — optional.

Persists the Factcheck.kz corpus with e5 embeddings and does cosine search in
the database. Gated behind DATABASE_URL + a present `psycopg` / `pgvector`
install, so the app falls back to in-memory search without them.

Schema: factcheck_corpus(id, lang, claim, verdict, rating, title, url, summary,
embedding vector(N)). Populate with scripts/index_corpus.py.
"""
from __future__ import annotations

from ..config import get_settings

_TABLE = "factcheck_corpus"


def available() -> bool:
    if not get_settings().database_url:
        return False
    try:
        import psycopg  # noqa: F401
        import pgvector  # noqa: F401
    except ImportError:
        return False
    return True


def _connect():
    import psycopg
    from pgvector.psycopg import register_vector

    conn = psycopg.connect(get_settings().database_url)
    register_vector(conn)
    return conn


def ensure_schema(dim: int) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_TABLE} (
                id       TEXT PRIMARY KEY,
                lang     TEXT,
                claim    TEXT,
                verdict  TEXT,
                rating   TEXT,
                title    TEXT,
                url      TEXT,
                summary  TEXT,
                embedding vector({dim})
            )
            """
        )
        cur.execute(
            f"CREATE INDEX IF NOT EXISTS {_TABLE}_emb_idx "
            f"ON {_TABLE} USING hnsw (embedding vector_cosine_ops)"
        )
        conn.commit()


def upsert(entries: list[dict], embeddings: list[list[float]]) -> int:
    import numpy as np

    with _connect() as conn, conn.cursor() as cur:
        for e, emb in zip(entries, embeddings):
            cur.execute(
                f"""
                INSERT INTO {_TABLE}
                    (id, lang, claim, verdict, rating, title, url, summary, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    claim=EXCLUDED.claim, verdict=EXCLUDED.verdict,
                    rating=EXCLUDED.rating, title=EXCLUDED.title,
                    url=EXCLUDED.url, summary=EXCLUDED.summary,
                    embedding=EXCLUDED.embedding
                """,
                (
                    e["id"], e.get("lang", ""), e.get("claim", ""),
                    e.get("verdict", ""), e.get("rating", ""), e.get("title", ""),
                    e.get("url", ""), e.get("summary", ""), np.array(emb),
                ),
            )
        conn.commit()
    return len(entries)


def search(query_vec: list[float], top_k: int = 3) -> list[dict]:
    """Return [{row..., similarity}] ordered by cosine similarity desc."""
    import numpy as np

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, lang, claim, verdict, rating, title, url, summary,
                   1 - (embedding <=> %s) AS similarity
            FROM {_TABLE}
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (np.array(query_vec), np.array(query_vec), top_k),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
