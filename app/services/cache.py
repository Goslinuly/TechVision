"""Verdict cache keyed by a hash of the normalized claim text.

§3 mitigation: «одни и те же фейки ходят по кругу» — the same forwarded hoaxes
recirculate, so we avoid re-hitting the LLM / external APIs for a claim we have
already resolved. In-memory for the MVP; swap for Redis in prod.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from ..models import ClaimResult

_store: dict[str, ClaimResult] = {}


def _key(text: str) -> str:
    norm = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def get(text: str) -> Optional[ClaimResult]:
    return _store.get(_key(text))


def put(text: str, result: ClaimResult) -> None:
    _store[_key(text)] = result.model_copy(deep=True)


def stats() -> dict:
    return {"cached_claims": len(_store)}
