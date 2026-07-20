"""Build the local Factcheck.kz corpus (§6 №3).

    python -m scripts.build_corpus [--limit N] [--out PATH]

Writes verdict-bearing fact-check entries to data/factcheck_kz.json, which the
local vector search prefers over the bundled sample. Re-run periodically to
refresh the corpus. Keep --limit modest to be polite to the source.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.tools.factcheck_parser import build_corpus

_DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "factcheck_kz.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = ap.parse_args()

    print(f"Fetching up to {args.limit} articles from factcheck.kz…")
    entries = build_corpus(limit=args.limit)
    args.out.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(entries)} verdict-bearing entries → {args.out}")
    if entries:
        from collections import Counter

        print("verdicts:", dict(Counter(e["verdict"] for e in entries)))


if __name__ == "__main__":
    main()
