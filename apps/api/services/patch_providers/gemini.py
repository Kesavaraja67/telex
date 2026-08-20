import re
import logging

import google.generativeai as genai

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
    """Patch provider backed by Google Gemini."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)
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
        try:
            response = await self.client.generate_content_async(prompt)
            return extract_diff(response.text)
        except Exception as exc:
            logger.error("GeminiProvider.generate_patch failed: %s", exc)
            return "UNABLE_TO_PATCH"
