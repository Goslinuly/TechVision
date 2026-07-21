"""KazLLM-8B specialist (§2.2) via a llama.cpp OpenAI-compatible server.

The orchestrator calls this for Kazakh idioms, local entities and dialect forms
that an English-centric model handles worse — the literal answer to the zone's
pain «инструментов на казахском с локальным контекстом нет».

Run the model with llama.cpp's server (GGUF from ISSAI):
    llama-server -m kazllm-8b.gguf --port 8080
then set KAZLLM_BASE_URL=http://localhost:8080/v1

Gated behind KAZLLM_BASE_URL; without it the orchestrator tool returns a stub.
"""
from __future__ import annotations

import httpx

from ..config import get_settings

_SYSTEM = (
    "Сен — қазақ тілі мен Қазақстан контекстінің маманысың. Саған мәтін "
    "беріледі. Ондағы идиомаларды, жергілікті атауларды/тұлғаларды және "
    "диалект формаларын қысқаша түсіндір. Егер мәтінде тексеруге тұрарлық "
    "жергілікті факт болса, оны бөліп көрсет. Қысқа әрі нақты жауап бер."
)


def available() -> bool:
    return bool(get_settings().kazllm_base_url)


def explain(text: str) -> dict:
    settings = get_settings()
    url = settings.kazllm_base_url.rstrip("/") + "/chat/completions"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                url,
                headers={"Authorization": f"Bearer {settings.kazllm_api_key}"},
                json={
                    "model": settings.kazllm_model,
                    "temperature": 0.3,
                    "max_tokens": 512,
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": text},
                    ],
                },
            )
            r.raise_for_status()
            data = r.json()
        analysis = data["choices"][0]["message"]["content"].strip()
        return {"available": True, "analysis": analysis, "model": settings.kazllm_model}
    except (httpx.HTTPError, KeyError, ValueError) as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc), "text": text}
