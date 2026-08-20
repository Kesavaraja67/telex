"""
Change extractor — uses Gemini to parse a changelog and extract structured
breaking changes from a package version bump.
"""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """You are analyzing a package changelog to extract breaking API changes.

PACKAGE: {package_name}
OLD VERSION: {old_version}
NEW VERSION: {new_version}

CHANGELOG:
{changelog}

Extract every breaking API change. For each one, return a JSON object with these fields:
- change_type: one of "signature_change" | "removed" | "renamed" | "deprecated" | "behavior_change"
- symbol_old: the exact old function/method/class name (e.g. "createCompletion")
- symbol_new: the new name if renamed, otherwise null
- description: one sentence describing the change
- confidence: a float 0.0-1.0 indicating how confident you are this is a real breaking change

Return a JSON array of these objects. If there are no breaking changes, return [].
Do not include any other text or explanation outside the JSON array."""


async def extract_breaking_changes(
    package_name: str,
    old_version: str,
    new_version: str,
    changelog: str,
) -> list[dict]:
    """
    Feed changelog text to Gemini and get back structured detected_changes rows.
    """
    from services.patch_providers import get_patch_provider

    # Reuse the Gemini client from the provider (it's configured there)
    try:
        import google.generativeai as genai
        from config import settings

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = EXTRACT_PROMPT.format(
            package_name=package_name,
            old_version=old_version,
            new_version=new_version,
            changelog=changelog[:8000],  # guard against huge changelogs
        )

        response = await model.generate_content_async(prompt)
        raw = response.text.strip()

        # Strip markdown fences if present
        fenced = re.search(r"```(?:json)?\s*\n(.*?)```", raw, re.DOTALL)
        if fenced:
            raw = fenced.group(1).strip()

        changes = json.loads(raw)
        if not isinstance(changes, list):
            logger.warning("extract_breaking_changes: expected list, got %s", type(changes))
            return []

        return changes

    except Exception as exc:
        logger.error("extract_breaking_changes failed: %s", exc)
        return []
