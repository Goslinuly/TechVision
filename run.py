"""Dev entry point: `python run.py` starts the FastAPI app (and the Telegram
bot too, if TELEGRAM_BOT_TOKEN is set)."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
