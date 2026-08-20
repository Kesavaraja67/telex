from .base import PatchProvider


def get_patch_provider(name: str | None = None) -> PatchProvider:
    """
    Factory for PatchProvider instances.

    Reads config from the settings module so callers never reference
    provider-specific classes directly — swapping providers is a one-line
    env var change (LLM_PROVIDER_DEFAULT).
    """
    from config import settings

    provider_name = name or settings.llm_provider_default

    if provider_name == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(settings.gemini_api_key)

    if provider_name == "claude":
        from .claude import ClaudeProvider
        return ClaudeProvider(settings.anthropic_api_key)

    raise ValueError(
        f"Unknown LLM provider: {provider_name!r}. "
        "Valid options: 'gemini', 'claude'."
    )
