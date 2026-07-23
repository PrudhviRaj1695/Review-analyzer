"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application configuration loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env
    )

    llm_api_key: str = Field(..., description="API key for LLM provider")
    llm_provider: str = Field(
        default="openai", description="LLM provider (e.g., anthropic, openai)"
    )
    llm_model: str = Field(default="gpt-4o", description="LLM model to use")
    llm_base_url: str | None = Field(
        default=None,
        description="Override API base URL (e.g. http://localhost:11434/v1 for local Ollama)",
    )
    llm_timeout_seconds: float = Field(
        default=30.0, description="Hard timeout for LLM API calls, in seconds"
    )
    llm_max_retries: int = Field(
        default=2,
        description="Max retries on transient LLM failures (429/5xx); 400s are never retried",
    )
    llm_input_price_per_1m: float = Field(
        default=2.50,
        description="USD per 1M input tokens for llm_model (gpt-4o default)",
    )
    llm_output_price_per_1m: float = Field(
        default=10.00,
        description="USD per 1M output tokens for llm_model (gpt-4o default)",
    )
    llm_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model (e.g. nomic-embed-text for local Ollama)",
    )
    llm_context_max_chars: int = Field(
        default=12_000,
        description="Hard cap on the assembled product/review context sent to the LLM, in characters",
    )
    retrieval_top_k: int = Field(
        default=5,
        description="Number of most-relevant reviews retrieved per product for /compare",
    )
    llm_slow_call_seconds: float = Field(
        default=5.0,
        description="Log a WARNING when a single LLM call takes longer than this, in seconds",
    )
    http_slow_request_seconds: float = Field(
        default=1.0,
        description="Log a WARNING when a request takes longer than this, in seconds",
    )


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


settings = get_settings()
