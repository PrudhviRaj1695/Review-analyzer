"""Test that settings load correctly from environment."""


def test_settings_load_from_env():
    """Verify that LLM_API_KEY loads from .env file."""
    # Dynamically import settings to pick up .env changes
    from app.settings import Settings

    settings = Settings()

    # Verify LLM_API_KEY is loaded
    assert settings.llm_api_key is not None, "LLM_API_KEY should be loaded from .env"
    assert len(settings.llm_api_key) > 0, "LLM_API_KEY should not be empty"
    print(f"[OK] LLM_API_KEY loaded: {settings.llm_api_key[:20]}...")


def test_settings_have_required_fields():
    """Verify that all required settings are present."""
    from app.settings import Settings

    settings = Settings()

    # All fields should be set
    assert hasattr(settings, "llm_api_key"), "Should have llm_api_key field"
    assert hasattr(settings, "llm_provider"), "Should have llm_provider field"
    assert hasattr(settings, "llm_model"), "Should have llm_model field"

    print("[OK] All settings fields present")
    print(f"     Provider: {settings.llm_provider}")
    print(f"     Model: {settings.llm_model}")


def test_settings_use_env_file():
    """Verify that .env file is being used."""
    from app.settings import Settings

    settings = Settings()
    # The test .env has this specific key format
    assert "sk_test" in settings.llm_api_key or settings.llm_api_key.startswith(
        "sk_"
    ), "Should load key from .env file"
    print("[OK] Settings loaded from .env file")


def test_env_file_not_in_git():
    """Verify that .env is in .gitignore."""
    from pathlib import Path

    gitignore_path = Path(__file__).parent.parent / ".gitignore"

    with open(gitignore_path, "r") as f:
        gitignore_content = f.read()

    assert ".env" in gitignore_content, ".env should be in .gitignore"
    print("[OK] .env is in .gitignore")
