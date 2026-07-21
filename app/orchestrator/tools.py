"""Tool definitions (Anthropic tool-use schema) + the dispatch that executes
them. Shared between the real Fable 5 loop and the deterministic path.
"""
from __future__ import annotations

import json

from ..services import kazllm
from ..tools import google_factcheck, local_corpus, rhetoric


# --- KazLLM specialist (§2.2) -----------------------------------------------
# KazLLM-8B-GGUF via llama.cpp (services/kazllm), consulted for Kazakh idioms /
# local entities. Degrades to a stub when KAZLLM_BASE_URL is not configured.
def kazllm_specialist(text: str) -> dict:
    if kazllm.available():
        return kazllm.explain(text)
    return {
        "available": False,
        "note": "KazLLM-8B not configured (set KAZLLM_BASE_URL); using stub.",
        "text": text,
    }


# Anthropic tool-use schema exposed to Fable 5.
TOOL_SCHEMAS: list[dict] = [
    {
        "name": "search_local_corpus",
        "description": "Семантический поиск утверждения по локальной базе "
        "Factcheck.kz (векторный). Возвращает вердикт и совпадения.",
        "input_schema": {
            "type": "object",
            "properties": {"claim": {"type": "string"}},
            "required": ["claim"],
        },
    },
    {
        "name": "google_factcheck",
        "description": "Google Fact Check Tools API (claims.search). "
        "Возвращает опубликованные фактчек-рейтинги по утверждению.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "lang": {"type": "string", "enum": ["kk", "ru"]},
            },
            "required": ["claim"],
        },
    },
    {
        "name": "analyze_rhetoric",
        "description": "Детектор манипулятивных приёмов с подсветкой конкретных "
        "фраз. Вызывать один раз на всём исходном сообщении.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "lang": {"type": "string", "enum": ["kk", "ru"]},
            },
            "required": ["text"],
        },
    },
    {
        "name": "kazllm_specialist",
        "description": "Специалист по казахскому: идиомы, локальные сущности, "
        "диалектные формы, непонятные англоязычной модели.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]


def dispatch(name: str, args: dict) -> str:
    """Execute a tool call and return a JSON string (what the model reads)."""
    if name == "search_local_corpus":
        result = local_corpus.search(args["claim"])
    elif name == "google_factcheck":
        result = google_factcheck.search(args["claim"], args.get("lang", "ru"))
    elif name == "analyze_rhetoric":
        result = rhetoric.analyze_dict(args["text"], args.get("lang", "ru"))
    elif name == "kazllm_specialist":
        result = kazllm_specialist(args["text"])
    else:
        result = {"error": f"unknown tool {name}"}
    return json.dumps(result, ensure_ascii=False)
