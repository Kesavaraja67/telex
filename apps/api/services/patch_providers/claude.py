import logging

from .base import PatchProvider
from .gemini import extract_diff
from .prompts import PATCH_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class ClaudeProvider(PatchProvider):
    """
    Patch provider backed by Anthropic Claude.

    Requires ANTHROPIC_API_KEY to be set. Not available in V1 — this stub
    is here so the provider factory compiles cleanly and swapping in Claude
    is a one-line config change when the key becomes available.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        if not api_key:
            raise RuntimeError(
                "ClaudeProvider requires ANTHROPIC_API_KEY — "
                "set LLM_PROVIDER_DEFAULT=gemini until you have a key."
            )
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed — run: pip install anthropic")

        self.client = AsyncAnthropic(api_key=api_key)  # type: ignore[assignment]
        self.model = model

    async def generate_patch(
        self,
        old_api: str,
        new_api: str,
        code_snippet: str,
        context: str,
    ) -> str:
        prompt = PATCH_PROMPT_TEMPLATE.format(
            old_api=old_api,
            new_api=new_api,
            code_snippet=code_snippet,
            context=context,
        )
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            return extract_diff(response.content[0].text)
        except Exception as exc:
            logger.error("ClaudeProvider.generate_patch failed: %s", exc)
            return "UNABLE_TO_PATCH"
