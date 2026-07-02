"""Central configuration for the Vantage prototype.

Everything is env-overridable but ships with defaults that let the app run
with zero external services and zero API keys. When an OpenAI-compatible
endpoint is configured (a hosted API or a local proxy), the scoring and memo
services use a live LLM and fall back to the heuristic provider on any error.
"""
from __future__ import annotations

import os
from functools import lru_cache

# Providers that speak the OpenAI /v1/chat/completions protocol.
_OPENAI_COMPATIBLE = {"openai", "local", "proxy", "copilot", "azure"}


class Settings:
    def __init__(self) -> None:
        self.database_url: str = os.getenv("VANTAGE_DATABASE_URL", "sqlite:///./vantage.db")
        self.llm_provider: str = os.getenv("VANTAGE_LLM_PROVIDER", "heuristic").lower()
        self.llm_api_key: str | None = os.getenv("VANTAGE_LLM_API_KEY")
        self.llm_model: str = os.getenv("VANTAGE_LLM_MODEL", "gpt-4o-mini")
        # Base URL for an OpenAI-compatible endpoint. When set (e.g. a local
        # proxy), a live LLM is used even without an API key.
        self.llm_base_url: str | None = os.getenv("VANTAGE_LLM_BASE_URL")
        self.llm_timeout: float = float(os.getenv("VANTAGE_LLM_TIMEOUT", "90"))
        self.prompt_version: str = os.getenv("VANTAGE_PROMPT_VERSION", "p0-2024.06")
        self.score_formula_version: str = os.getenv("VANTAGE_SCORE_FORMULA_VERSION", "v1")

    @property
    def uses_live_llm(self) -> bool:
        """True when a live OpenAI-compatible LLM should be used.

        Either a hosted provider with an API key, or any provider pointed at a
        custom base URL (a local proxy typically needs no key).
        """
        if self.llm_provider not in _OPENAI_COMPATIBLE:
            return False
        return bool(self.llm_api_key) or bool(self.llm_base_url)

    @property
    def resolved_base_url(self) -> str:
        """The chat-completions base URL (no trailing slash)."""
        base = self.llm_base_url or "https://api.openai.com"
        return base.rstrip("/")

    @property
    def ai_mode(self) -> str:
        """Human-readable AI mode shown in the UI banner."""
        if self.uses_live_llm:
            where = "local proxy" if self.llm_base_url else self.llm_provider
            return f"live: {self.llm_model} via {where}"
        return "heuristic (deterministic, offline)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
