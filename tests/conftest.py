"""Force a deterministic, offline test environment.

The repo's .env may hold real Groq/Google/Telegram keys for local runs. Tests
must not depend on live network or a paid/rate-limited LLM, so we override those
to empty + provider=mock before any Settings are read, and clear the caches.
"""
import os

_OFFLINE = {
    "LLM_PROVIDER": "mock",
    "GROQ_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
    "GOOGLE_FACTCHECK_API_KEY": "",
    "TELEGRAM_BOT_TOKEN": "",
    "EMBEDDINGS_ENABLED": "false",
    "DATABASE_URL": "",
    "KAZLLM_BASE_URL": "",
    "ENABLE_OCR": "false",
}
# env vars take precedence over .env in pydantic-settings.
os.environ.update(_OFFLINE)

from app.config import get_settings  # noqa: E402
from app.services import llm as _llm  # noqa: E402

get_settings.cache_clear()
_llm.reset_llm()
