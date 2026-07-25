"""Telegram bot (aiogram 3) — receives forwarded messages, replies with the
short card + a link to the web breakdown (§2).

Started only when TELEGRAM_BOT_TOKEN is set. Two run modes:
  * long-polling (default for local dev) — start_polling();
  * webhook — feed updates via feed_webhook_update() from the FastAPI route.
"""
from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message

from .config import get_settings
from .orchestrator import analyze
from .presenter import chat_card
from . import store
from .services.ocr import extract_text

log = logging.getLogger("aqiqat.bot")

dp = Dispatcher()

# Telegram message hard limit is 4096 chars; keep inputs well under it.
_MAX_INPUT = 3500

_WELCOME = (
    "👋 Сәлем! Салам! Я <b>Aqıqat</b> — помогаю разобрать «новость» из чата.\n\n"
    "Перешли мне сообщение (текст или фото), и я покажу: какие утверждения "
    "проверяемы, что нашлось в базах фактчекеров и какие манипулятивные приёмы "
    "использованы. На казахском и русском.\n\n"
    "⚠️ Я не выношу вердикт «97% фейк» — я даю <b>объяснимый разбор</b>.\n\n"
    "Просто перешли сюда сообщение 👇  ·  /help — как это работает"
)

_HELP = (
    "ℹ️ <b>Как пользоваться Aqıqat</b>\n\n"
    "1. Перешли (forward) сюда «новость» из любого чата — текстом.\n"
    "2. Я разобью её на проверяемые утверждения и проверю по базам "
    "фактчекеров (Factcheck.kz, Google Fact Check).\n"
    "3. Покажу манипулятивные приёмы и вариант вежливого ответа.\n\n"
    "Я <b>не</b> выношу вердикт «правда/ложь» на всё сообщение — мнения и "
    "прогнозы не проверяю, только факты.\n\n"
    "🌐 Работаю на казахском и русском.\n"
    "Команды: /start — начать · /help — эта справка"
)


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(_WELCOME, parse_mode="HTML")


@dp.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(_HELP, parse_mode="HTML")


@dp.message()
async def on_message(message: Message) -> None:
    settings = get_settings()
    text = message.text or message.caption or ""

    # Photo → OCR (§1), if enabled and configured.
    if not text and message.photo:
        if settings.enable_ocr:
            try:
                file = await message.bot.get_file(message.photo[-1].file_id)
                buf = await message.bot.download_file(file.file_path)
                text = extract_text(buf.read())
            except Exception:  # noqa: BLE001
                text = ""
        if not text.strip():
            await message.answer(
                "На фото не нашёл текст 🖼️ Пришли текст сообщения — разберу его."
            )
            return

    if not text.strip():
        await message.answer(
            "Пришли <b>текст</b> сообщения (или перешли его сюда) — и я разберу его.\n"
            "/help — как это работает.",
            parse_mode="HTML",
        )
        return

    if len(text) > _MAX_INPUT:
        text = text[:_MAX_INPUT]
        await message.answer(
            "✂️ Сообщение длинное — разберу первые ~3500 символов."
        )

    await message.chat.do("typing")
    try:
        card = analyze(text)
    except Exception:  # noqa: BLE001 — never leave the user without a reply
        log.exception("analyze failed")
        await message.answer("😞 Не смог разобрать сообщение. Попробуй ещё раз.")
        return
    store.save(card)
    await message.answer(chat_card(card, settings.public_base_url))


async def set_commands(bot: Bot) -> None:
    """Register the command menu shown in Telegram's UI."""
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать / бастау"),
            BotCommand(command="help", description="Как это работает"),
        ]
    )


def build_bot() -> Bot:
    settings = get_settings()
    return Bot(token=settings.telegram_bot_token)
