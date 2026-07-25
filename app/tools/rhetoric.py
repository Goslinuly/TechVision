"""Rhetoric / manipulation detector (§5).

Rule-based catalogue of manipulative techniques with the exact span in the
source text — so the card can highlight the specific phrase (§4). Patterns
cover both Russian and Kazakh cues. A classifier can later replace/augment the
rules; the `analyze()` contract stays the same.
"""
from __future__ import annotations

import re

from ..models import Lang, Manipulation

# technique -> (localized label kk/ru, [regex cues], explanation kk/ru)
_CATALOGUE: dict[str, dict] = {
    "fear_appeal": {
        "label": {"ru": "Апелляция к страху", "kk": "Қорқынышқа арқау салу"},
        "cues": [
            r"скрыва\w+", r"уничтож\w+", r"опасн\w+", r"катастроф\w+", r"смертел\w+",
            r"угроз\w+", r"вымира\w+",
            r"жасыр\w+", r"қауіпт\w+", r"апат\w+", r"өлім\w+",
        ],
        "explanation": {
            "ru": "Формулировка давит на страх, а не приводит проверяемый факт.",
            "kk": "Тұжырым тексерілетін дерек емес, қорқыныш сезіміне әсер етеді.",
        },
    },
    "unsourced_number": {
        "label": {"ru": "Конкретная цифра без источника", "kk": "Дереккөзсіз нақты сан"},
        # A big/precise number not accompanied by a source word nearby.
        "cues": [r"\b\d[\d\s.,]{2,}\b"],
        "explanation": {
            "ru": "Точная цифра создаёт видимость достоверности, но источник не указан.",
            "kk": "Нақты сан сенімділік әсерін береді, бірақ дереккөзі көрсетілмеген.",
        },
    },
    "false_dichotomy": {
        "label": {"ru": "Ложная дихотомия", "kk": "Жалған дилемма"},
        "cues": [
            # «Или X, или Y» / «Либо X, либо Y» with any words between.
            r"\bили\b[^.!?\n]{2,45}?\bили\b",
            r"\bлибо\b[^.!?\n]{2,45}?\bлибо\b",
            r"только так", r"не\s+\w+\s+—\s+значит",
            r"не\s+болса", r"тек\s+қана\s+солай",
        ],
        "explanation": {
            "ru": "Навязывает выбор из двух вариантов, скрывая остальные.",
            "kk": "Басқа мүмкіндіктерді жасырып, екі нұсқаны ғана таңдатады.",
        },
    },
    "authority_appeal": {
        "label": {"ru": "Апелляция к авторитету", "kk": "Беделге сілтеу"},
        "cues": [
            r"учёные доказали", r"эксперты утвержда\w+", r"врачи говор\w+",
            r"как известно", r"все знают",
            r"ғалымдар дәлелдеді", r"сарапшылар айт\w+",
        ],
        "explanation": {
            "ru": "Ссылка на безымянный авторитет заменяет проверяемое доказательство.",
            "kk": "Аты-жөнсіз беделге сілтеу тексерілетін дәлелді алмастырады.",
        },
    },
    "us_vs_them": {
        "label": {"ru": "Противопоставление «свои / чужие»", "kk": "«Біз / олар» қарсы қоюы"},
        "cues": [
            r"\bони\b.*\bнас\b", r"власт\w+[\w\s]{0,25}?скрыва\w+", r"нам врут",
            r"власти врут", r"олар бізді", r"билік[\w\s]{0,25}?жасыр\w+",
        ],
        "explanation": {
            "ru": "Делит на «своих» и «чужих», подменяя аргумент эмоцией.",
            "kk": "«Біз» бен «оларды» бөліп, дәлелді эмоцияға ауыстырады.",
        },
    },
    "urgency": {
        "label": {"ru": "Искусственная срочность", "kk": "Жасанды жеделдік"},
        "cues": [
            r"срочно", r"немедленно", r"пока не поздно", r"перешл\w+ всем",
            r"жедел", r"кешікпей", r"барлығына жібер\w+",
        ],
        "explanation": {
            "ru": "Давление «действуй сейчас» мешает проверить информацию.",
            "kk": "«Қазір әрекет ет» қысымы ақпаратты тексеруге кедергі жасайды.",
        },
    },
}

_SOURCE_NEARBY = re.compile(
    r"(источник|по данным|согласно|дереккөз|мәлімет)", re.IGNORECASE
)


def analyze(text: str, lang: Lang = Lang.RU) -> list[Manipulation]:
    found: list[Manipulation] = []
    seen_spans: set[tuple[int, int]] = set()

    for technique, spec in _CATALOGUE.items():
        for cue in spec["cues"]:
            for m in re.finditer(cue, text, re.IGNORECASE):
                span = (m.start(), m.end())
                # For unsourced numbers, skip if a source word is mentioned.
                if technique == "unsourced_number" and _SOURCE_NEARBY.search(text):
                    continue
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                found.append(
                    Manipulation(
                        technique=technique,
                        label=spec["label"].get(lang.value, spec["label"]["ru"]),
                        span_text=m.group(0),
                        start=m.start(),
                        end=m.end(),
                        explanation=spec["explanation"].get(
                            lang.value, spec["explanation"]["ru"]
                        ),
                    )
                )
    found.sort(key=lambda x: x.start)
    return found


def analyze_dict(text: str, lang: str = "ru") -> dict:
    """Tool-facing wrapper returning JSON-serializable output for the LLM."""
    items = analyze(text, Lang(lang) if lang in ("kk", "ru") else Lang.RU)
    return {"techniques": [i.model_dump() for i in items]}
