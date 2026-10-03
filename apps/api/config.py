import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _API_DIR.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[
            _API_DIR / ".env",
            _REPO_ROOT / ".env",
            ".env",
        ],
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

    # Encryption / Security
    telex_encryption_key: str = ""

    # Deployment environment
    # Set to "production" in Render/Vercel to activate secret validation.
    environment: str = "development"

    # App
    nextauth_secret: str = "telex-development-session-secret-key-32-chars-min"
    next_public_api_url: str = "http://localhost:8000"
    web_app_url: str = "http://localhost:3000"
    github_app_slug: str = "telex-agent-dev"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    demo_key: str = "telex_demo_secret_2026"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_trust_proxy: bool = False


_DEFAULT_SECRET = "telex-development-session-secret-key-32-chars-min"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def collect_missing_secrets(s: Settings) -> list[str]:
    missing: list[str] = []
    if not s.nextauth_secret or s.nextauth_secret == _DEFAULT_SECRET:
        missing.append("NEXTAUTH_SECRET")
    if not s.github_app_id:
        missing.append("GITHUB_APP_ID")
    if not s.github_app_private_key:
        missing.append("GITHUB_APP_PRIVATE_KEY")
    if not s.telex_encryption_key:
        missing.append("TELEX_ENCRYPTION_KEY")
    return missing


# P1-3: Fail loudly at startup if running in production without real secrets.
# Uses normalized predicate (checks RENDER or case-insensitive ENVIRONMENT=production).
_is_production = bool(os.getenv("RENDER") or settings.environment.strip().lower() == "production")

if _is_production:
    _missing = collect_missing_secrets(settings)
    if _missing:
        raise RuntimeError(
            f"Production startup blocked — the following secrets are missing or have default values: "
            f"{', '.join(_missing)}. Set them as environment variables in Render."
        )
