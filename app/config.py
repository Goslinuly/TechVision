"""Runtime configuration, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Real integration (provisioned).
    google_factcheck_api_key: str = ""

    # Anthropic — optional; falls back to a deterministic mock when empty.
    anthropic_api_key: str = ""
    orchestrator_model: str = "claude-fable-5"
    substep_model: str = "claude-haiku-4-5"

    # Telegram — optional; bot not started when empty.
    telegram_bot_token: str = ""

    public_base_url: str = "http://localhost:8000"
    enable_ocr: bool = False

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def bot_enabled(self) -> bool:
        return bool(self.telegram_bot_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
