"""Telegram bot (aiogram 3) — receives forwarded messages, replies with the
short card + a link to the web breakdown (§2).

Started only when TELEGRAM_BOT_TOKEN is set. Two run modes:
  * long-polling (default for local dev) — start_polling();
  * webhook — feed updates via feed_webhook_update() from the FastAPI route.
"""
from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from .config import get_settings
from .orchestrator import analyze
from .presenter import chat_card
from . import store
from .services.ocr import extract_text

log = logging.getLogger("aqiqat.bot")

dp = Dispatcher()

_WELCOME = (
    "👋 Салам! Я Aqıqat — помогаю разобрать «новость» из чата.\n\n"
    "Перешли мне сообщение (текст или фото), и я покажу: какие утверждения "
    "проверяемы, что нашлось в базах фактчекеров и какие манипулятивные приёмы "
    "использованы. На казахском и русском.\n\n"
    "⚠️ Я не выношу вердикт «97% фейк» — я даю объяснимый разбор."
)


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(_WELCOME)


@dp.message()
async def on_message(message: Message) -> None:
    settings = get_settings()
    text = message.text or message.caption or ""

    # Photo → OCR (§1), if enabled and configured.
    if not text and message.photo and settings.enable_ocr:
        try:
            file = await message.bot.get_file(message.photo[-1].file_id)
            buf = await message.bot.download_file(file.file_path)
            text = extract_text(buf.read())
        except Exception:  # noqa: BLE001
            text = ""

    if not text.strip():
        await message.answer(
            "Пришли текст сообщения или фото с текстом — и я разберу его."
        )
        return

    await message.chat.do("typing")
    card = analyze(text)
    store.save(card)
    await message.answer(chat_card(card, settings.public_base_url))


def build_bot() -> Bot:
    settings = get_settings()
    return Bot(token=settings.telegram_bot_token)
