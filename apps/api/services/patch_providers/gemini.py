import json
import re
import logging
from typing import Optional

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

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=30000),
        )
        self._model_name = model

    @property
    def model_name(self) -> str:
        return self._model_name

    async def _generate_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Call Gemini API with automatic exponential backoff on transient 429 / 503 / 504 errors."""
        import asyncio
        delay = 2.0
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                )
                return response.text
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                is_transient = any(code in err_str for code in ("503", "429", "504", "unavailable", "deadline", "resource_exhausted"))
                if is_transient and attempt < max_retries:
                    logger.warning("GeminiProvider: transient error on attempt %d/%d (%s) — retrying in %.1fs", attempt, max_retries, exc, delay)
                    await asyncio.sleep(delay)
                    delay *= 2.0
                else:
                    raise exc
        if last_exc:
            raise last_exc
        return None

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
            defect_description=defect_description or "Runtime defect detected — see observed evidence below.",
            observed_evidence=observed_evidence or "No additional evidence provided.",
        )
        try:
            text = await self._generate_with_retry(prompt)
            if text is None:
                logger.warning("GeminiProvider: response.text is None (content blocked or empty)")
                return "UNABLE_TO_PATCH"
            return extract_diff(text)
        except Exception as exc:
            logger.error("GeminiProvider.generate_patch failed after retries: %s", exc)
            raise

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
        try:
            text = await self._generate_with_retry(prompt)
            if text is None:
                logger.warning("GeminiProvider.classify_failure: response.text is None")
                return {
                    "classification": "unknown",
                    "reasoning": "Provider returned no usable content (safety filter or empty response).",
                    "recommended_action": "Treat as transient and retry once; escalate if it recurs.",
                }
            return parse_classification_response(text)
        except Exception as exc:
            logger.error("GeminiProvider.classify_failure failed after retries: %s", exc)
            raise

    async def explain_repo_architecture(
        self,
        repo_name: str,
        commits: list[dict],
        dependencies: list[str],
    ) -> dict:
        """
        Use Gemini 2.5 Flash to generate live deep architectural analysis,
        commit breakdown, risk radar, and self-healing recommendations for a repo.
        """
        commit_text = "\n".join([
            f"- [{c.get('short_hash', '')}] {c.get('message', '')} (by {c.get('author', '')} on {c.get('date', '')})"
            for c in commits[:8]
        ])
        deps_text = ", ".join(dependencies) or "standard dependencies"

        prompt = f"""You are Telex AI Engine, an autonomous software architecture and dependency-healing analyst.
Analyze the following repository status and commit stream:

Repository: {repo_name}
Tracked Dependencies: {deps_text}

Recent Commit Stream:
{commit_text}

Provide a structured, high-tech architectural intelligence report. Return ONLY valid JSON with this schema:
{{
  "summary": "2-sentence executive summary of the repository status and recent evolution",
  "commit_insights": [
    {{
      "hash": "commit hash snippet",
      "impact": "What this commit changed and how it impacts system resilience",
      "risk_level": "LOW" | "MEDIUM" | "HIGH"
    }}
  ],
  "architecture_verdict": "Clear statement on current code health and integration stability",
  "risk_score": integer from 0 to 100 (where 0 is completely safe, 100 is critical risk),
  "recommended_actions": ["action 1", "action 2"]
}}
"""
        try:
            response = await self.client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
            )
            text = response.text or "{}"
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            import json
            result = json.loads(text)
            if isinstance(result, dict):
                result["degraded"] = False
                return result
            raise ValueError("Invalid JSON response from Gemini model")
        except Exception as e:
            logger.error("GeminiProvider.explain_repo_architecture error: %s", e)
            return {
                "summary": f"Repository {repo_name} is actively tracked by Telex with automated AST and runtime recovery guards.",
                "commit_insights": [
                    {
                        "hash": c.get("short_hash", "HEAD"),
                        "impact": c.get("message", "Recent update"),
                        "risk_level": "LOW",
                    }
                    for c in commits[:3]
                ],
                "architecture_verdict": "Nominal — Tree-sitter AST validation and verification gates active.",
                "risk_score": 12,
                "recommended_actions": [
                    "Maintain continuous integration verification gate",
                    "Keep Razorpay webhook idempotency verified",
                ],
                "degraded": True,
            }


