import json
import re
import logging

from google import genai  # type: ignore[import]
from google.genai import types as genai_types  # type: ignore[import]

from .base import FailureClassification, PatchProvider
from .prompts import PATCH_PROMPT_TEMPLATE, CLASSIFY_FAILURE_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


def extract_diff(text: str) -> str:
    """
    Pull the unified diff out of an LLM response.

    The model may wrap it in a markdown code block. This strips that wrapper
    and returns the raw diff. If the model signalled it can't patch, the
    sentinel is passed through unchanged.
    """
    if "UNABLE_TO_PATCH" in text:
        return "UNABLE_TO_PATCH"

    # Strip ```diff ... ``` fences if present
    fenced = re.search(r"```(?:diff)?\s*\n(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    # Return raw text if it looks like a diff already
    if text.strip().startswith(("---", "@@", "diff")):
        return text.strip()

    logger.warning("extract_diff: could not locate a diff block in LLM response")
    return "UNABLE_TO_PATCH"


def parse_classification_response(raw: str) -> FailureClassification:
    """
    Extract and validate failure classification from LLM JSON response.
    Shared between GeminiProvider and ClaudeProvider.
    """
    if not raw or not raw.strip():
        return {
            "classification": "unknown",
            "reasoning": "Provider returned no usable text content.",
            "recommended_action": "Treat as transient and retry once; escalate if it recurs.",
        }

    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    cleaned = fenced.group(1).strip() if fenced else raw.strip()

    try:
        result = json.loads(cleaned)
        if not isinstance(result, dict):
            raise ValueError(f"Expected JSON object, got {type(result).__name__}")
        classification = result.get("classification", "unknown")
        if classification not in ("transient", "code_defect", "unknown"):
            classification = "unknown"
        return {
            "classification": classification,
            "reasoning": str(result.get("reasoning", "")),
            "recommended_action": str(result.get("recommended_action", "")),
        }
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("parse_classification_response: invalid JSON response: %s", exc)
        return {
            "classification": "unknown",
            "reasoning": f"Provider response was not valid JSON: {cleaned[:200]}",
            "recommended_action": "Treat as transient and retry once; escalate if it recurs.",
        }


class GeminiProvider(PatchProvider):
    """Patch provider backed by Google Gemini (google-genai SDK)."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=30000),
        )
        self._model_name = model

    @property
    def model_name(self) -> str:
        return self._model_name

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
        # Transient errors (network, quota, server) propagate so the worker
        # retries the job.  Only intentional no-patch output becomes UNABLE_TO_PATCH.
        response = await self.client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
        )
        # response.text is None when content is blocked by safety filters
        if response.text is None:
            logger.warning("GeminiProvider: response.text is None (content blocked or empty)")
            return "UNABLE_TO_PATCH"
        return extract_diff(response.text)

    async def classify_failure(
        self,
        failure_type: str,
        error_context: str,
    ) -> FailureClassification:
        """
        Classify a runtime failure via Gemini (Tier 2 — ambiguous cases only).

        Transient provider errors propagate so the worker retries the job.
        Only a model refusal or unparse-able response returns the unknown sentinel.
        """
        prompt = CLASSIFY_FAILURE_PROMPT_TEMPLATE.format(
            failure_type=failure_type,
            error_context=error_context,
        )
        response = await self.client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
        )
        if response.text is None:
            logger.warning("GeminiProvider.classify_failure: response.text is None")
            return {
                "classification": "unknown",
                "reasoning": "Provider returned no usable content (safety filter or empty response).",
                "recommended_action": "Treat as transient and retry once; escalate if it recurs.",
            }
        return parse_classification_response(response.text)


