"""The orchestrator — §2.1.

`analyze(text)` runs the full agentic cycle:
  1. detect language (kk/ru)
  2. classify + decompose into atomic claims  (Haiku substep, or mock)
  3. route each checkable claim through tools  (Fable 5 tool-use loop, or mock)
  4. detect manipulation techniques with spans (rule-based, always)
  5. synthesize the explainable Card (§4)

Two execution paths produce the SAME `Card` shape:
  * LLM path  — real Fable 5 loop decides tool routing and writes the card;
  * mock path — deterministic; still calls the REAL Google / local / rhetoric
    tools, so the pipeline is fully testable offline with just the Google key.
"""
from __future__ import annotations

import json
import re

from ..models import (
    Card,
    ClaimKind,
    ClaimResult,
    Evidence,
    Lang,
    MessageClass,
    Verdict,
)
from ..services import cache, metrics
from ..services.lang import detect_lang
from ..services.llm import get_llm
from ..tools import google_factcheck, local_corpus, rhetoric
from . import prompts
from .tools import TOOL_SCHEMAS, dispatch


# --------------------------------------------------------------------------- #
# §5 — confidence formula, stated explicitly.
#   confidence = f(similarity, presence-in-google, source-rating-clarity)
# --------------------------------------------------------------------------- #
def compute_confidence(local: dict, google: dict) -> float:
    conf = 0.0
    local_matches = local.get("matches", [])
    if local.get("verdict"):
        sim = max((m.get("similarity") or 0.0) for m in local_matches) if local_matches else 0.0
        conf += 0.5 * min(1.0, sim / local_corpus.TAU) if sim else 0.35
    if google.get("verdict"):
        conf += 0.45
    return round(min(conf, 1.0), 2)


def _verdict_from_sources(local: dict, google: dict) -> Verdict:
    for src in (local.get("verdict"), google.get("verdict")):
        if src in ("refuted", "supported"):
            return Verdict(src)
    if local.get("matches") or google.get("matches"):
        return Verdict.NOT_FOUND
    return Verdict.NOT_FOUND


# --------------------------------------------------------------------------- #
# Step 2 — classify + decompose
# --------------------------------------------------------------------------- #
_OPINION_MARKERS = re.compile(
    r"(скрыва|врут|врёт|обман|домысел|думаю|наверное|по-моему|кажется|считаю|"
    r"жасыр|алдау|меніңше|ойлаймын)",
    re.IGNORECASE,
)
# Split on sentence + clause boundaries (including bare commas) so a trailing
# opinion clause separates from the checkable claim it is attached to.
_SPLIT = re.compile(r"[.!?;\n,]|(?<=\s)и\s+(?=\w+\s)")
_LEADING_CONNECTIVE = re.compile(r"^(что|а также)\s+", re.IGNORECASE)


def _mock_extract(text: str) -> tuple[MessageClass, list[tuple[str, ClaimKind]]]:
    raw = [
        _LEADING_CONNECTIVE.sub("", frag.strip(" ,.—–-"))
        for frag in _SPLIT.split(text)
    ]
    frags = [f for f in raw if len(re.findall(r"\w+", f)) >= 2]
    if not frags:
        frags = [text.strip()]

    claims: list[tuple[str, ClaimKind]] = []
    for frag in frags:
        if _OPINION_MARKERS.search(frag):
            claims.append((frag, ClaimKind.OPINION))
        elif re.search(r"\d", frag) or len(re.findall(r"\w+", frag)) >= 3:
            claims.append((frag, ClaimKind.CHECKABLE))
        else:
            claims.append((frag, ClaimKind.OPINION))

    has_check = any(k is ClaimKind.CHECKABLE for _, k in claims)
    has_manip = bool(rhetoric.analyze(text))
    if has_check and has_manip:
        cls = MessageClass.MIXED
    elif has_check:
        cls = MessageClass.FACT
    elif has_manip:
        cls = MessageClass.MANIPULATION
    else:
        cls = MessageClass.OPINION
    return cls, claims


def _extract(text: str) -> tuple[MessageClass, list[tuple[str, ClaimKind]]]:
    llm = get_llm()
    if not llm.available:
        return _mock_extract(text)
    try:
        data = llm.complete_json(prompts.EXTRACT_SYSTEM, text, prompts.EXTRACT_SCHEMA)
        cls = MessageClass(data["message_class"])
        claims = [
            (c["text"], ClaimKind(c["kind"]))
            for c in data.get("claims", [])
            if c.get("text")
        ]
        return cls, (claims or _mock_extract(text)[1])
    except Exception:  # noqa: BLE001 — never let a substep crash the pipeline
        return _mock_extract(text)


# --------------------------------------------------------------------------- #
# Step 3 — resolve a single checkable claim via the real tools (mock path,
# and also the cache-backed resolution reused elsewhere).
# --------------------------------------------------------------------------- #
def _resolve_claim(text: str, kind: ClaimKind, lang: Lang) -> ClaimResult:
    if kind is ClaimKind.OPINION:
        return ClaimResult(
            text=text,
            kind=kind,
            verdict=Verdict.NOT_CHECKABLE,
            confidence=0.0,
            note="Это оценочное суждение / домысел, а не проверяемый факт."
            if lang is Lang.RU
            else "Бұл бағалау пікірі, тексерілетін дерек емес.",
        )

    cached = cache.get(text)
    if cached:
        return cached

    local = local_corpus.search(text)
    google = google_factcheck.search(text, lang.value)
    verdict = _verdict_from_sources(local, google)
    confidence = compute_confidence(local, google)

    evidence = [Evidence(**m) for m in local.get("matches", [])]
    evidence += [Evidence(**m) for m in google.get("matches", [])]

    note = {
        Verdict.REFUTED: "Опровергнуто в базах фактчекеров."
        if lang is Lang.RU
        else "Фактчек базаларында теріске шығарылған.",
        Verdict.SUPPORTED: "Подтверждается источниками."
        if lang is Lang.RU
        else "Дереккөздермен расталады.",
        Verdict.NOT_FOUND: "Данные не найдены — относитесь с осторожностью."
        if lang is Lang.RU
        else "Дерек табылмады — сақтықпен қараңыз.",
    }.get(verdict, "")

    result = ClaimResult(
        text=text,
        kind=kind,
        verdict=verdict,
        confidence=confidence,
        evidence=evidence[:6],
        note=note,
    )
    cache.put(text, result)
    return result


def _mock_reply_suggestion(claims: list[ClaimResult], lang: Lang) -> str:
    refuted = [c for c in claims if c.verdict is Verdict.REFUTED]
    not_found = [c for c in claims if c.verdict is Verdict.NOT_FOUND]
    opinions = [c for c in claims if c.verdict is Verdict.NOT_CHECKABLE]
    if lang is Lang.KK:
        parts = []
        if refuted:
            parts.append("Бұл тұжырымдар фактчек базаларында теріске шығарылған.")
        if not_found:
            parts.append("Кейбір деректердің ресми расталуы жоқ.")
        if opinions:
            parts.append("«...» деген сөз — тексерілетін дерек емес, тек болжам.")
        return " ".join(parts) or "Бұл ақпаратты тексеру қажет."
    parts = []
    if refuted:
        parts.append("Эти утверждения опровергнуты фактчекерами.")
    if not_found:
        parts.append("По части данных нет официального подтверждения.")
    if opinions:
        parts.append("Формулировки вроде «врачи скрывают» — это домысел, а не факт.")
    return " ".join(parts) or "Эту информацию стоит перепроверить в источниках."


# --------------------------------------------------------------------------- #
# LLM path — parse the card JSON the Fable 5 loop emits.
# --------------------------------------------------------------------------- #
def _parse_card_json(raw: str) -> dict | None:
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _analyze_llm(
    text: str, lang: Lang, cls: MessageClass, claims: list[tuple[str, ClaimKind]]
) -> tuple[list[ClaimResult], str, list[str]] | None:
    llm = get_llm()
    claim_lines = "\n".join(
        f"- ({k.value}) {t}" for t, k in claims
    )
    user = (
        f"Язык сообщения: {lang.value}\n"
        f"Классификация: {cls.value}\n\n"
        f"Исходное сообщение:\n{text}\n\n"
        f"Извлечённые утверждения:\n{claim_lines}\n\n"
        f"Проверь проверяемые утверждения через инструменты и выведи ИТОГ-JSON."
    )
    called: list[str] = []

    def traced_dispatch(name: str, args: dict) -> str:
        called.append(name)
        return dispatch(name, args)

    raw = llm.run_tool_loop(
        prompts.ORCHESTRATOR_SYSTEM, user, TOOL_SCHEMAS, traced_dispatch
    )
    data = _parse_card_json(raw)
    if not data:
        return None

    results: list[ClaimResult] = []
    for c in data.get("claims", []):
        try:
            results.append(
                ClaimResult(
                    text=c["text"],
                    kind=ClaimKind(c.get("kind", "checkable")),
                    verdict=Verdict(c.get("verdict", "not_found")),
                    confidence=float(c.get("confidence", 0.0)),
                    note=c.get("note", ""),
                    evidence=[Evidence(**e) for e in c.get("evidence", [])],
                )
            )
        except Exception:  # noqa: BLE001 — skip malformed claim entries
            continue
    if not results:
        return None
    return results, data.get("reply_suggestion", ""), sorted(set(called))


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze(text: str) -> Card:
    text = (text or "").strip()
    lang = detect_lang(text)
    cls, claims = _extract(text)

    # Manipulations are always computed deterministically (§4: подсветка фраз).
    manipulations = rhetoric.analyze(text, lang)

    used_llm = False
    tools_called: list[str] = ["analyze_rhetoric"]
    results: list[ClaimResult]
    reply: str

    llm_out = None
    if get_llm().available:
        llm_out = _analyze_llm(text, lang, cls, claims)

    if llm_out is not None:
        results, reply, called = llm_out
        used_llm = True
        tools_called = sorted(set(tools_called) | set(called))
    else:
        results = [_resolve_claim(t, k, lang) for t, k in claims]
        reply = _mock_reply_suggestion(results, lang)
        checkable = [r for r in results if r.kind is ClaimKind.CHECKABLE]
        if checkable:
            tools_called += ["search_local_corpus", "google_factcheck"]

    card = Card(
        lang=lang,
        source_text=text,
        message_class=cls,
        claims=results,
        manipulations=manipulations,
        reply_suggestion=reply,
        used_llm=used_llm,
        tools_called=sorted(set(tools_called)),
    )
    metrics.record(card)
    return card
