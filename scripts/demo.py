"""End-to-end CLI demo — no Telegram, no server needed.

    python -m scripts.demo
    python -m scripts.demo "ваш текст здесь"

Runs the full orchestrator pipeline and prints the chat card. Uses the real
Google Fact Check API if a key is set; the LLM loop if ANTHROPIC_API_KEY is set;
otherwise the deterministic mock.
"""
from __future__ import annotations

import sys

from app.config import get_settings
from app.orchestrator import analyze
from app.presenter import chat_card

_SAMPLES = [
    "Врачи скрывают, что вакцина X вызвала 5000 смертей в Алматы. Срочно перешлите всем!",
    "Мемлекет барлық зейнетақыны цифрлық теңгеге мәжбүрлеп ауыстырады, билік жасырып отыр.",
    "Средняя зарплата в Казахстане превысила 400 тысяч тенге.",
]


def main() -> None:
    settings = get_settings()
    texts = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else _SAMPLES
    print(
        f"[config] llm={'on' if settings.llm_enabled else 'mock'} "
        f"google={'on' if settings.google_factcheck_api_key else 'off'}\n"
    )
    for text in texts:
        print("=" * 70)
        print("ВХОД:", text, "\n")
        card = analyze(text)
        print(chat_card(card, settings.public_base_url))
        print()


if __name__ == "__main__":
    main()
