from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost/telex"

    # GitHub App
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_webhook_secret: str = ""

    # GitHub OAuth
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""

    # LLM providers
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider_default: str = "gemini"

    # Razorpay — Test Mode only; never commit keys, read from environment
    razorpay_test_key_id: str = ""
    razorpay_test_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    payment_recovery_repo_name: str = ""

    # Deployment environment
    # Set to "production" in Render/Vercel to activate secret validation.
    environment: str = "development"

    # App
    nextauth_secret: str = "telex-development-session-secret-key-32-chars-min"
    next_public_api_url: str = "https://telex-api.onrender.com"
    web_app_url: str = "https://telex-pi.vercel.app"
    github_app_slug: str = "telex-agent-dev"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://telex-pi.vercel.app",
        "https://telex-agent-dev.vercel.app",
        "https://aura-drops-gold.vercel.app",
    ]
    demo_key: str = "telex_demo_secret_2026"


_DEFAULT_SECRET = "telex-development-session-secret-key-32-chars-min"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


# P1-3: Fail loudly at startup if running in production without real secrets.
# This prevents silent misbehaviour from mis-deployed builds.
if settings.environment == "production":
    _missing: list[str] = []
    if settings.nextauth_secret == _DEFAULT_SECRET:
        _missing.append("NEXTAUTH_SECRET")
    if not settings.razorpay_test_key_id:
        _missing.append("RAZORPAY_TEST_KEY_ID")
    if not settings.razorpay_test_key_secret:
        _missing.append("RAZORPAY_TEST_KEY_SECRET")
    if not settings.github_app_id:
        _missing.append("GITHUB_APP_ID")
    if not settings.github_app_private_key:
        _missing.append("GITHUB_APP_PRIVATE_KEY")
    if _missing:
        raise RuntimeError(
            f"Production startup blocked — the following secrets are missing or have default values: "
            f"{', '.join(_missing)}. Set them as environment variables in Render."
        )

