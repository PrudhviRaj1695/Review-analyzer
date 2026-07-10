"""Application settings loaded from environment variables."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env
    )

    llm_api_key: str = Field(..., description="API key for LLM provider")
    llm_provider: str = Field(
        default="anthropic", description="LLM provider (e.g., anthropic, openai)"
    )
    llm_model: str = Field(default="claude-opus-4-8", description="LLM model to use")


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


settings = get_settings()
