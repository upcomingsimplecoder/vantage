"""Central configuration for the Vantage prototype.

Everything is env-overridable but ships with defaults that let the app run
with zero external services and zero API keys.
"""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.database_url: str = os.getenv("VANTAGE_DATABASE_URL", "sqlite:///./vantage.db")
        self.llm_provider: str = os.getenv("VANTAGE_LLM_PROVIDER", "heuristic").lower()
        self.llm_api_key: str | None = os.getenv("VANTAGE_LLM_API_KEY")
        self.llm_model: str = os.getenv("VANTAGE_LLM_MODEL", "gpt-4o-mini")
        self.prompt_version: str = os.getenv("VANTAGE_PROMPT_VERSION", "p0-2024.06")
        self.score_formula_version: str = os.getenv("VANTAGE_SCORE_FORMULA_VERSION", "v1")

    @property
    def ai_mode(self) -> str:
        """Human-readable AI mode shown in the UI banner."""
        if self.llm_provider in {"openai", "anthropic"} and self.llm_api_key:
            return f"live:{self.llm_provider}:{self.llm_model}"
        return "heuristic (deterministic, offline)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
