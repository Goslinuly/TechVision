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

    # LLM provider selection: "auto" | "groq" | "anthropic" | "mock".
    # "auto" prefers Groq (free) if its key is set, else Anthropic, else mock.
    llm_provider: str = "auto"

    # Groq — free tier, OpenAI-compatible tool-use.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Anthropic — optional; Fable 5 orchestrator + Haiku substeps.
    anthropic_api_key: str = ""
    orchestrator_model: str = "claude-fable-5"
    substep_model: str = "claude-haiku-4-5"

    # Telegram — optional; bot not started when empty.
    telegram_bot_token: str = ""

    public_base_url: str = "http://localhost:8000"
    enable_ocr: bool = False

    @property
    def active_provider(self) -> str:
        """Resolve which LLM backend is actually usable."""
        p = self.llm_provider.lower()
        if p == "groq":
            return "groq" if self.groq_api_key else "mock"
        if p == "anthropic":
            return "anthropic" if self.anthropic_api_key else "mock"
        if p == "mock":
            return "mock"
        # auto
        if self.groq_api_key:
            return "groq"
        if self.anthropic_api_key:
            return "anthropic"
        return "mock"

    @property
    def llm_enabled(self) -> bool:
        return self.active_provider != "mock"

    @property
    def bot_enabled(self) -> bool:
        return bool(self.telegram_bot_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
