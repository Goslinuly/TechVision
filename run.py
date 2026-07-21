"""Entry point: `python run.py`.

Reads $PORT inside Python (no shell expansion needed — works on Railway/Hetzner
regardless of how the start command is invoked). Starts FastAPI, and the
Telegram bot too if TELEGRAM_BOT_TOKEN is set.

Local dev with autoreload: UVICORN_RELOAD=1 python run.py
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("UVICORN_RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)
