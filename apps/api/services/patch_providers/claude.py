import json
import logging

from .base import PatchProvider
from .gemini import extract_diff
from .prompts import PATCH_PROMPT_TEMPLATE, CLASSIFY_FAILURE_PROMPT_TEMPLATE

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
        # Transient provider/transport errors propagate so worker can retry
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        if getattr(response, "stop_reason", None) == "refusal" or not response.content:
            return "UNABLE_TO_PATCH"
        for block in response.content:
            if hasattr(block, "text") and isinstance(block.text, str):
                return extract_diff(block.text)
        return "UNABLE_TO_PATCH"

    async def classify_failure(
        self,
        failure_type: str,
        error_context: str,
    ) -> dict:
        """
        Classify a runtime failure via Claude (Tier 2 — ambiguous cases only).

        Transient provider/transport errors propagate so the worker retries the job.
        Only a model refusal or empty response returns the unknown sentinel.
        """
        prompt = CLASSIFY_FAILURE_PROMPT_TEMPLATE.format(
            failure_type=failure_type,
            error_context=error_context,
        )
        # Transient transport errors propagate — mirror generate_patch error handling
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        if getattr(response, "stop_reason", None) == "refusal" or not response.content:
            return {
                "classification": "unknown",
                "reasoning": "Provider returned a refusal or empty response.",
                "recommended_action": "Treat as transient and retry once; escalate if it recurs.",
            }
        raw = ""
        for block in response.content:
            if hasattr(block, "text") and isinstance(block.text, str):
                raw = block.text.strip()
                break
        if not raw:
            return {
                "classification": "unknown",
                "reasoning": "Provider returned no text content.",
                "recommended_action": "Treat as transient and retry once; escalate if it recurs.",
            }
        # Strip optional markdown fences
        import re
        fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
        if fenced:
            raw = fenced.group(1).strip()
        try:
            result = json.loads(raw)
            classification = result.get("classification", "unknown")
            if classification not in ("transient", "code_defect", "unknown"):
                classification = "unknown"
            return {
                "classification": classification,
                "reasoning": result.get("reasoning", ""),
                "recommended_action": result.get("recommended_action", ""),
            }
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("ClaudeProvider.classify_failure: could not parse JSON response: %s", exc)
            return {
                "classification": "unknown",
                "reasoning": f"Provider response was not valid JSON: {raw[:200]}",
                "recommended_action": "Treat as transient and retry once; escalate if it recurs.",
            }

