"""
OpenAI patch provider.

Default model: gpt-4o-mini (fast, cost-effective; change _DEFAULT_MODEL to swap).
Requires: openai>=1.0.0 package.
"""

import logging

from .base import FailureClassification, PatchProvider
from .gemini import extract_diff, parse_classification_response
from .prompts import CLASSIFY_FAILURE_PROMPT_TEMPLATE, PATCH_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

# Update this constant to change the default OpenAI model used for patch generation.
_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(PatchProvider):
    """Patch provider backed by OpenAI Chat Completions API."""

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL):
        self._model_name = model
        if not api_key:
            raise RuntimeError(
                "OpenAIProvider requires an API key — "
                "set LLM_PROVIDER_DEFAULT=gemini until you have one."
            )
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai package not installed — run: pip install openai")
        self.client = AsyncOpenAI(api_key=api_key)

    def __repr__(self) -> str:
        return f"<OpenAIProvider model={self._model_name!r}>"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_patch(
        self,
        old_api: str,
        new_api: str,
        code_snippet: str,
        context: str,
        defect_description: str = "",
        observed_evidence: str = "",
    ) -> str:
        prompt = PATCH_PROMPT_TEMPLATE.format(
            old_api=old_api or "(not applicable)",
            new_api=new_api or "(not applicable)",
            code_snippet=code_snippet,
            context=context,
            defect_description=defect_description
            or "Runtime defect detected — see observed evidence below.",
            observed_evidence=observed_evidence or "No additional evidence provided.",
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            text = response.choices[0].message.content or ""
            return extract_diff(text)
        except Exception as exc:
            logger.error("OpenAIProvider.generate_patch failed: %s", exc)
            raise

    async def generate_patch_candidates(
        self,
        old_api: str,
        new_api: str,
        code_snippet: str,
        context: str,
        defect_description: str = "",
        observed_evidence: str = "",
        n: int = 3,
    ) -> list[str]:
        """Generate N candidate diffs for Best-of-N selection."""
        candidates = []
        for _ in range(n):
            diff = await self.generate_patch(
                old_api=old_api,
                new_api=new_api,
                code_snippet=code_snippet,
                context=context,
                defect_description=defect_description,
                observed_evidence=observed_evidence,
            )
            candidates.append(diff)
        return candidates

    async def classify_failure(
        self,
        failure_type: str,
        error_context: str,
    ) -> FailureClassification:
        prompt = CLASSIFY_FAILURE_PROMPT_TEMPLATE.format(
            failure_type=failure_type,
            error_context=error_context,
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            raw = response.choices[0].message.content or ""
            return parse_classification_response(raw)
        except Exception as exc:
            logger.error("OpenAIProvider.classify_failure failed: %s", exc)
            raise
