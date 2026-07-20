"""Lightweight in-memory analytics — the measurable-effect base for §5.

Records every breakdown so the team can report usage: number of checks,
verdict distribution, share of messages with detected manipulation, language
split. In-memory for the MVP; export to a real store for the pitch metric
«% сообщений, где пользователь изменил решение делиться».
"""
from __future__ import annotations

from collections import Counter

from ..models import Card, ClaimKind, Verdict

_checks = 0
_verdicts: Counter[str] = Counter()
_langs: Counter[str] = Counter()
_classes: Counter[str] = Counter()
_msgs_with_manipulation = 0
_llm_backed = 0


def record(card: Card) -> None:
    global _checks, _msgs_with_manipulation, _llm_backed
    _checks += 1
    _langs[card.lang.value] += 1
    _classes[card.message_class.value] += 1
    if card.manipulations:
        _msgs_with_manipulation += 1
    if card.used_llm:
        _llm_backed += 1
    for c in card.claims:
        if c.kind is ClaimKind.CHECKABLE:
            _verdicts[c.verdict.value] += 1


def snapshot() -> dict:
    return {
        "checks_total": _checks,
        "messages_with_manipulation": _msgs_with_manipulation,
        "manipulation_rate": round(_msgs_with_manipulation / _checks, 3)
        if _checks
        else 0.0,
        "llm_backed_checks": _llm_backed,
        "checkable_verdicts": dict(_verdicts),
        "by_language": dict(_langs),
        "by_message_class": dict(_classes),
    }


def reset() -> None:
    """For tests."""
    global _checks, _msgs_with_manipulation, _llm_backed
    _checks = _msgs_with_manipulation = _llm_backed = 0
    _verdicts.clear()
    _langs.clear()
    _classes.clear()
