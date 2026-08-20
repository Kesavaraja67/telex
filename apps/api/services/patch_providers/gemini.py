import re
import logging

from google import genai  # type: ignore[import]
from google.genai import types as genai_types  # type: ignore[import]

from .base import PatchProvider
from .prompts import PATCH_PROMPT_TEMPLATE

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


class GeminiProvider(PatchProvider):
    """Patch provider backed by Google Gemini (google-genai SDK)."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model

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
            model=self.model_name,
            contents=prompt,
        )
        # response.text is None when content is blocked by safety filters
        if response.text is None:
            logger.warning("GeminiProvider: response.text is None (content blocked or empty)")
            return "UNABLE_TO_PATCH"
        return extract_diff(response.text)
