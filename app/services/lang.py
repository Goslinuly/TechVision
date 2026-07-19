"""Language detection (kk / ru).

Kazakh and Russian share Cyrillic, so a script check is not enough. We key on
the Kazakh-specific letters (ә, ғ, қ, ң, ө, ұ, ү, һ, і) which never appear in
Russian. Falls back to ru — the larger corpus and the safer default for the
family-chat scenario in §0.
"""
from __future__ import annotations

from ..models import Lang

_KAZAKH_ONLY = set("әғқңөұүһі" "ӘҒҚҢӨҰҮҺІ")


def detect_lang(text: str) -> Lang:
    if any(ch in _KAZAKH_ONLY for ch in text):
        return Lang.KK
    return Lang.RU
