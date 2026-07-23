"""Test that settings load correctly from environment."""

import logging

logger = logging.getLogger(__name__)


def test_settings_load_from_env():
    """Verify that LLM_API_KEY loads from .env file."""
    # Dynamically import settings to pick up .env changes
    from app.settings import Settings

    settings = Settings()

    # Verify LLM_API_KEY is loaded
    assert settings.llm_api_key is not None, "LLM_API_KEY should be loaded from .env"
    assert len(settings.llm_api_key) > 0, "LLM_API_KEY should not be empty"
    logger.info("[OK] LLM_API_KEY loaded: %s...", settings.llm_api_key[:20])


def test_settings_have_required_fields():
    """Verify that all required settings are present."""
    from app.settings import Settings

    settings = Settings()

    # All fields should be set
    assert hasattr(settings, "llm_api_key"), "Should have llm_api_key field"
    assert hasattr(settings, "llm_provider"), "Should have llm_provider field"
    assert hasattr(settings, "llm_model"), "Should have llm_model field"

    logger.info("[OK] All settings fields present")
    logger.info("     Provider: %s", settings.llm_provider)
    logger.info("     Model: %s", settings.llm_model)


def test_settings_use_env_file():
    """Verify that .env file is being used."""
    from app.settings import Settings

    settings = Settings()
    # Confirms this came from .env, not a fallback default (Settings has no default
    # for llm_api_key, so an unset .env would fail validation before reaching here).
    assert settings.llm_api_key == "ollama", "Should load key from .env file"
    logger.info("[OK] Settings loaded from .env file")


def test_llm_timeout_and_retry_defaults():
    """Verify hard timeout and retry-count settings exist with sane defaults."""
    from app.settings import Settings

    settings = Settings()

    assert settings.llm_timeout_seconds > 0, "Timeout should be a positive number"
    assert settings.llm_max_retries >= 1, (
        "Should retry at least once on transient errors"
    )
    logger.info(
        "[OK] timeout=%ss max_retries=%s",
        settings.llm_timeout_seconds,
        settings.llm_max_retries,
    )


def test_env_file_not_in_git():
    """Verify that .env is in .gitignore."""
    from pathlib import Path

    gitignore_path = Path(__file__).parent.parent / ".gitignore"

    with open(gitignore_path, "r") as f:
        gitignore_content = f.read()

    assert ".env" in gitignore_content, ".env should be in .gitignore"
    logger.info("[OK] .env is in .gitignore")
