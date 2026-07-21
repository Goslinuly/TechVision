"""FastAPI backend (§2) — webhook handler + web-card server + /analyze API.

Endpoints:
  GET  /health          — liveness + config flags
  POST /analyze         — {"text": "..."} → Card JSON + rendered chat card
  GET  /r/{id}          — shareable HTML breakdown card
  POST /webhook/{token} — Telegram webhook sink (prod)

On startup, if a bot token is configured, the bot runs via long-polling in a
background task (simplest for local dev / demo). For production deployment,
disable polling and point Telegram at POST /webhook/{token} instead.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import store
from .config import get_settings
from .models import VERDICT_EMOJI
from .orchestrator import analyze
from .presenter import chat_card, highlight_source
from .services import cache, metrics
from .services.ocr import extract_text

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aqiqat")

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_USE_POLLING = True  # set False if deploying with a real Telegram webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    poll_task = None
    bot = None
    if settings.bot_enabled and _USE_POLLING:
        from .bot import build_bot, dp

        bot = build_bot()
        log.info("Starting Telegram bot (long-polling)…")
        poll_task = asyncio.create_task(dp.start_polling(bot))
    else:
        log.info(
            "Bot disabled (no TELEGRAM_BOT_TOKEN) — use POST /analyze to test."
        )
    try:
        yield
    finally:
        if poll_task:
            poll_task.cancel()
        if bot:
            await bot.session.close()


app = FastAPI(title="Aqıqat", version="0.1.0", lifespan=lifespan)


class AnalyzeIn(BaseModel):
    text: str = ""
    image_base64: str = ""  # optional: extract text via OCR (§1) when ENABLE_OCR


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return _TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health() -> dict:
    s = get_settings()
    provider = s.active_provider
    model = {
        "groq": s.groq_model,
        "anthropic": s.orchestrator_model,
    }.get(provider)
    return {
        "status": "ok",
        "llm_provider": provider,
        "llm_enabled": s.llm_enabled,
        "orchestrator_model": model,
        "bot_enabled": s.bot_enabled,
        "ocr_enabled": s.enable_ocr,
        "google_factcheck": bool(s.google_factcheck_api_key),
        "cards_stored": store.count(),
        **cache.stats(),
    }


@app.get("/metrics")
def metrics_endpoint() -> dict:
    """Usage analytics — measurable-effect base for the pitch (§5)."""
    return metrics.snapshot()


@app.post("/analyze")
def analyze_endpoint(body: AnalyzeIn) -> JSONResponse:
    text = body.text.strip()
    if not text and body.image_base64:
        try:
            image_bytes = base64.b64decode(body.image_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="invalid base64 image")
        text = extract_text(image_bytes).strip()
        if not text:
            raise HTTPException(
                status_code=422,
                detail="no text extracted (OCR disabled or empty image)",
            )
    if not text:
        raise HTTPException(status_code=400, detail="empty text")
    card = analyze(text)
    store.save(card)
    return JSONResponse(
        {
            "card": card.model_dump(),
            "chat_text": chat_card(card, get_settings().public_base_url),
            "url": f"{get_settings().public_base_url}/r/{card.id}",
        }
    )


@app.get("/r/{card_id}", response_class=HTMLResponse)
def web_card(request: Request, card_id: str):
    card = store.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="card not found")
    return _TEMPLATES.TemplateResponse(
        "card.html",
        {
            "request": request,
            "card": card,
            "emoji": VERDICT_EMOJI,
            "highlighted": highlight_source(card),
        },
    )


@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request) -> dict:
    settings = get_settings()
    if not settings.bot_enabled or token != settings.telegram_bot_token:
        raise HTTPException(status_code=403, detail="invalid token")
    from aiogram.types import Update

    from .bot import build_bot, dp

    update = Update.model_validate(await request.json())
    await dp.feed_update(build_bot(), update)
    return {"ok": True}
