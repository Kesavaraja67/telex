"""
Patch provider factory.

get_patch_provider(name, api_key) returns a PatchProvider for the named
LLM backend. If api_key is provided, that key is used directly (BYOK path).
If api_key is None, the platform's server-side key from settings is used
(hosted-key fallback path — existing behavior unchanged for non-BYOK users).

Provider name → class mapping:
  gemini    → GeminiProvider    (default, platform Gemini key)
  claude    → ClaudeProvider    (Anthropic)
  openai    → OpenAIProvider    (GPT-4o-mini default)
  mistral   → MistralProvider   (mistral-small-latest default)
  groq      → GroqProvider      (llama-3.3-70b-versatile default)
  cohere    → CohereProvider    (command-r-plus-08-2024 default)
  xai       → XAIProvider       (grok-3-mini default)
  deepseek  → DeepSeekProvider  (deepseek-chat default)
  together  → TogetherProvider  (llama-3.3-70B-Instruct-Turbo default)
  nemotron  → NemotronProvider  (nvidia/llama-3.1-nemotron-70b-instruct default)
"""

from db.session import AsyncSessionLocal

from .base import PatchProvider


def get_patch_provider(
    name: str | None = None,
    api_key: str | None = None,
) -> PatchProvider:
    """
    Factory for PatchProvider instances.

    Args:
        name:    Provider name. Defaults to settings.llm_provider_default.
        api_key: Plaintext API key. If None, uses the platform server-side key
                 from settings (hosted-key fallback — existing behaviour).

    Returns a PatchProvider implementation.
    Raises ValueError for unknown provider names.
    Raises RuntimeError if the required key is absent.
    """
    from config import settings

    provider_name = (name or settings.llm_provider_default).lower().strip()

    if provider_name == "gemini":
        from .gemini import GeminiProvider

        key = api_key or settings.gemini_api_key
        if not key:
            raise RuntimeError(
                "GeminiProvider requires GEMINI_API_KEY — "
                "configure platform key in environment or add a BYOK key in Settings."
            )
        return GeminiProvider(key)

    if provider_name in ("claude", "anthropic"):
        from .claude import ClaudeProvider

        key = api_key or settings.anthropic_api_key
        if not key:
            raise RuntimeError(
                "ClaudeProvider requires ANTHROPIC_API_KEY — "
                "configure platform key in environment or add a BYOK key in Settings."
            )
        return ClaudeProvider(key)

    if provider_name == "openai":
        from .openai_provider import OpenAIProvider

        if not api_key:
            raise RuntimeError(
                "OpenAI is a BYOK-only provider — no platform key is configured. "
                "Add your key in Settings → API Keys."
            )
        return OpenAIProvider(api_key)

    if provider_name == "mistral":
        from .mistral_provider import MistralProvider

        if not api_key:
            raise RuntimeError(
                "Mistral is a BYOK-only provider — add your key in Settings → API Keys."
            )
        return MistralProvider(api_key)

    if provider_name == "groq":
        from .groq_provider import GroqProvider

        if not api_key:
            raise RuntimeError(
                "Groq is a BYOK-only provider — add your key in Settings → API Keys."
            )
        return GroqProvider(api_key)

    if provider_name == "cohere":
        from .extra_providers import CohereProvider

        if not api_key:
            raise RuntimeError(
                "Cohere is a BYOK-only provider — add your key in Settings → API Keys."
            )
        return CohereProvider(api_key)

    if provider_name in ("xai", "grok"):
        from .extra_providers import XAIProvider

        if not api_key:
            raise RuntimeError("xAI is a BYOK-only provider — add your key in Settings → API Keys.")
        return XAIProvider(api_key)

    if provider_name == "deepseek":
        from .extra_providers import DeepSeekProvider

        if not api_key:
            raise RuntimeError(
                "DeepSeek is a BYOK-only provider — add your key in Settings → API Keys."
            )
        return DeepSeekProvider(api_key)

    if provider_name == "together":
        from .extra_providers import TogetherProvider

        if not api_key:
            raise RuntimeError(
                "Together AI is a BYOK-only provider — add your key in Settings → API Keys."
            )
        return TogetherProvider(api_key)

    if provider_name == "nemotron":
        from .extra_providers import NemotronProvider

        if not api_key:
            raise RuntimeError(
                "Nemotron is a BYOK-only provider — add your key in Settings → API Keys."
            )
        return NemotronProvider(api_key)

    raise ValueError(
        f"Unknown LLM provider: {provider_name!r}. "
        "Valid options: 'gemini', 'claude', 'openai', 'mistral', 'groq', "
        "'cohere', 'xai', 'deepseek', 'together', 'nemotron'."
    )


async def get_patch_provider_for_user(
    user_id: str,
    preferred_provider: str | None = None,
) -> PatchProvider:
    """
    BYOK-aware provider factory.

    Fallback hierarchy:
      1. User's decrypted BYOK key for preferred_provider
      2. If preferred_provider is platform-supported with a key (e.g. Gemini, Claude): use platform key
      3. If preferred_provider has no key, fall back to default platform provider (e.g. Gemini)
      4. If no key is available anywhere: fail closed with RuntimeError.

    Args:
        user_id:            UUID string of the authenticated user.
        preferred_provider: Provider name to try first. Falls back to default provider.
    """
    import logging
    import uuid as uuid_module
    from datetime import datetime, timezone

    from sqlalchemy import select

    from config import settings
    from db.models import UserApiKey
    from services.crypto import decrypt_key

    logger = logging.getLogger(__name__)

    provider_name = (preferred_provider or settings.llm_provider_default).lower().strip()

    uid = None
    try:
        uid = uuid_module.UUID(user_id)
    except (ValueError, AttributeError):
        pass

    if uid is not None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserApiKey).where(
                    UserApiKey.user_id == uid,
                    UserApiKey.provider == provider_name,
                )
            )
            row = result.scalar_one_or_none()

            if row is not None:
                try:
                    plaintext_key = decrypt_key(row.encrypted_key)
                    row.last_used_at = datetime.now(timezone.utc)
                    await session.commit()
                    provider = get_patch_provider(provider_name, api_key=plaintext_key)
                    del plaintext_key
                    return provider
                except Exception as exc:
                    logger.warning(
                        "get_patch_provider_for_user: failed to decrypt BYOK key for user=%s provider=%s: %s",
                        uid,
                        provider_name,
                        exc,
                    )
                    # Proceed to platform fallback

    # Check if preferred provider can be fulfilled by platform key
    if provider_name == "gemini" and settings.gemini_api_key:
        return get_patch_provider("gemini")
    if provider_name in ("claude", "anthropic") and settings.anthropic_api_key:
        return get_patch_provider("claude")

    # Fall back to default platform provider
    default_prov = (settings.llm_provider_default or "gemini").lower().strip()
    if default_prov == "gemini" and settings.gemini_api_key:
        return get_patch_provider("gemini")
    if default_prov in ("claude", "anthropic") and settings.anthropic_api_key:
        return get_patch_provider("claude")

    # If neither user BYOK key nor platform key exists: fail closed!
    raise RuntimeError(
        f"No usable LLM provider credentials found for provider '{provider_name}' "
        f"(user={user_id}). Configure a BYOK key in Settings or configure platform credentials."
    )
