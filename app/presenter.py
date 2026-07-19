"""Render a Card into the short chat message (§4).

Shared by the Telegram bot and the /analyze HTTP endpoint so the card looks
identical everywhere.
"""
from __future__ import annotations

from html import escape

from .models import VERDICT_EMOJI, Card, ClaimKind, Lang, Verdict

_L = {
    Lang.RU: {
        "title": "📋 РАЗБОР",
        "claims": "Проверяемые утверждения:",
        "manip": "🎭 Манипулятивные приёмы:",
        "reply": "💬 Как можно ответить:",
        "full": "🔗 Полный разбор",
        "none_manip": "Явных манипулятивных приёмов не найдено.",
        "opinion": "Не факт, а предположение — не проверяется",
    },
    Lang.KK: {
        "title": "📋 ТАЛДАУ",
        "claims": "Тексерілетін тұжырымдар:",
        "manip": "🎭 Манипуляциялық тәсілдер:",
        "reply": "💬 Қалай жауап беруге болады:",
        "full": "🔗 Толық талдау",
        "none_manip": "Айқын манипуляциялық тәсілдер табылмады.",
        "opinion": "Дерек емес, болжам — тексерілмейді",
    },
}

_VERDICT_TEXT = {
    Lang.RU: {
        Verdict.REFUTED: "Опровергнуто",
        Verdict.SUPPORTED: "Подтверждено",
        Verdict.NOT_FOUND: "Данные не найдены",
        Verdict.NOT_CHECKABLE: "Не проверяется",
    },
    Lang.KK: {
        Verdict.REFUTED: "Теріске шығарылған",
        Verdict.SUPPORTED: "Расталған",
        Verdict.NOT_FOUND: "Дерек табылмады",
        Verdict.NOT_CHECKABLE: "Тексерілмейді",
    },
}


def chat_card(card: Card, base_url: str) -> str:
    L = _L[card.lang]
    vt = _VERDICT_TEXT[card.lang]
    lines: list[str] = [L["title"], "", L["claims"]]

    for c in card.claims:
        emoji = VERDICT_EMOJI[c.verdict]
        if c.kind is ClaimKind.OPINION:
            lines.append(f"  • «{_clip(c.text)}» → {emoji} {L['opinion']}")
        else:
            conf = f" ({int(c.confidence * 100)}%)" if c.confidence else ""
            lines.append(f"  • «{_clip(c.text)}» → {emoji} {vt[c.verdict]}{conf}")

    lines += ["", L["manip"]]
    if card.manipulations:
        for m in card.manipulations:
            lines.append(f"  • {m.label} («{_clip(m.span_text, 40)}»)")
    else:
        lines.append(f"  • {L['none_manip']}")

    if card.reply_suggestion:
        lines += ["", L["reply"], f"  {card.reply_suggestion}"]

    lines += ["", f"{L['full']}: {base_url}/r/{card.id}"]
    return "\n".join(lines)


def _clip(text: str, n: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def highlight_source(card: Card) -> str:
    """Return the source text as HTML with manipulation spans wrapped in
    <mark> (with the technique label as a tooltip). Non-overlapping spans only.
    """
    text = card.source_text
    spans = sorted(card.manipulations, key=lambda m: m.start)
    out: list[str] = []
    cursor = 0
    for m in spans:
        if m.start < cursor or m.end > len(text):
            continue  # skip overlaps / stale offsets
        out.append(escape(text[cursor : m.start]))
        title = escape(f"{m.label}: {m.explanation}")
        out.append(
            f'<mark class="manip" title="{title}">{escape(text[m.start : m.end])}</mark>'
        )
        cursor = m.end
    out.append(escape(text[cursor:]))
    return "".join(out).replace("\n", "<br>")
