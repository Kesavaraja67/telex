"""
Remaining BYOK provider implementations.

Providers: Cohere, xAI (Grok), DeepSeek, Together AI, Nvidia Nemotron.

Each uses OpenAI-compatible Chat Completions endpoint where applicable.
Default model constants are at the top of each class — change to swap.
Required packages (install when enabling BYOK for a provider):
  cohere>=5.0.0, openai>=1.0.0 (xAI/DeepSeek/Together use OpenAI client pointed at alt base_url)
"""

import logging

from .base import FailureClassification, PatchProvider
from .gemini import extract_diff, parse_classification_response
from .prompts import CLASSIFY_FAILURE_PROMPT_TEMPLATE, PATCH_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


# ── Cohere ───────────────────────────────────────────────────────────────────


class CohereProvider(PatchProvider):
    """Patch provider backed by Cohere Command R+."""

    _DEFAULT_MODEL = "command-r-plus-08-2024"

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL):
        self._model_name = model
        if not api_key:
            raise RuntimeError("CohereProvider requires an API key.")
        try:
            from cohere import AsyncClientV2
        except ImportError:
            raise RuntimeError("cohere package not installed — run: pip install cohere")
        self.client = AsyncClientV2(api_key=api_key)

    def __repr__(self) -> str:
        return f"<CohereProvider model={self._model_name!r}>"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_patch(
        self, old_api, new_api, code_snippet, context, defect_description="", observed_evidence=""
    ) -> str:
        prompt = PATCH_PROMPT_TEMPLATE.format(
            old_api=old_api or "(not applicable)",
            new_api=new_api or "(not applicable)",
            code_snippet=code_snippet,
            context=context,
            defect_description=defect_description or "Runtime defect detected.",
            observed_evidence=observed_evidence or "No additional evidence provided.",
        )
        try:
            response = await self.client.chat(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.message.content[0].text if response.message.content else ""
            return extract_diff(text)
        except Exception as exc:
            logger.error("CohereProvider.generate_patch failed: %s", exc)
            raise

    async def generate_patch_candidates(
        self,
        old_api,
        new_api,
        code_snippet,
        context,
        defect_description="",
        observed_evidence="",
        n=3,
    ) -> list[str]:
        return [
            await self.generate_patch(
                old_api, new_api, code_snippet, context, defect_description, observed_evidence
            )
            for _ in range(n)
        ]

    async def classify_failure(self, failure_type, error_context) -> FailureClassification:
        prompt = CLASSIFY_FAILURE_PROMPT_TEMPLATE.format(
            failure_type=failure_type, error_context=error_context
        )
        try:
            response = await self.client.chat(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.message.content[0].text if response.message.content else ""
            return parse_classification_response(raw)
        except Exception as exc:
            logger.error("CohereProvider.classify_failure failed: %s", exc)
            raise


# ── xAI (Grok) ────────────────────────────────────────────────────────────


class XAIProvider(PatchProvider):
    """Patch provider backed by xAI Grok via OpenAI-compatible API."""

    _DEFAULT_MODEL = "grok-3-mini"
    _BASE_URL = "https://api.x.ai/v1"

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL):
        self._model_name = model
        if not api_key:
            raise RuntimeError("XAIProvider requires an xAI API key.")
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai package not installed — run: pip install openai")
        self.client = AsyncOpenAI(api_key=api_key, base_url=self._BASE_URL)

    def __repr__(self) -> str:
        return f"<XAIProvider model={self._model_name!r}>"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_patch(
        self, old_api, new_api, code_snippet, context, defect_description="", observed_evidence=""
    ) -> str:
        prompt = PATCH_PROMPT_TEMPLATE.format(
            old_api=old_api or "(not applicable)",
            new_api=new_api or "(not applicable)",
            code_snippet=code_snippet,
            context=context,
            defect_description=defect_description or "Runtime defect detected.",
            observed_evidence=observed_evidence or "No additional evidence provided.",
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            return extract_diff(response.choices[0].message.content or "")
        except Exception as exc:
            logger.error("XAIProvider.generate_patch failed: %s", exc)
            raise

    async def generate_patch_candidates(
        self,
        old_api,
        new_api,
        code_snippet,
        context,
        defect_description="",
        observed_evidence="",
        n=3,
    ) -> list[str]:
        return [
            await self.generate_patch(
                old_api, new_api, code_snippet, context, defect_description, observed_evidence
            )
            for _ in range(n)
        ]

    async def classify_failure(self, failure_type, error_context) -> FailureClassification:
        prompt = CLASSIFY_FAILURE_PROMPT_TEMPLATE.format(
            failure_type=failure_type, error_context=error_context
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            return parse_classification_response(response.choices[0].message.content or "")
        except Exception as exc:
            logger.error("XAIProvider.classify_failure failed: %s", exc)
            raise


# ── DeepSeek ────────────────────────────────────────────────────────────────


class DeepSeekProvider(PatchProvider):
    """Patch provider backed by DeepSeek via OpenAI-compatible API."""

    _DEFAULT_MODEL = "deepseek-chat"
    _BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL):
        self._model_name = model
        if not api_key:
            raise RuntimeError("DeepSeekProvider requires a DeepSeek API key.")
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai package not installed — run: pip install openai")
        self.client = AsyncOpenAI(api_key=api_key, base_url=self._BASE_URL)

    def __repr__(self) -> str:
        return f"<DeepSeekProvider model={self._model_name!r}>"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_patch(
        self, old_api, new_api, code_snippet, context, defect_description="", observed_evidence=""
    ) -> str:
        prompt = PATCH_PROMPT_TEMPLATE.format(
            old_api=old_api or "(not applicable)",
            new_api=new_api or "(not applicable)",
            code_snippet=code_snippet,
            context=context,
            defect_description=defect_description or "Runtime defect detected.",
            observed_evidence=observed_evidence or "No additional evidence provided.",
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            return extract_diff(response.choices[0].message.content or "")
        except Exception as exc:
            logger.error("DeepSeekProvider.generate_patch failed: %s", exc)
            raise

    async def generate_patch_candidates(
        self,
        old_api,
        new_api,
        code_snippet,
        context,
        defect_description="",
        observed_evidence="",
        n=3,
    ) -> list[str]:
        return [
            await self.generate_patch(
                old_api, new_api, code_snippet, context, defect_description, observed_evidence
            )
            for _ in range(n)
        ]

    async def classify_failure(self, failure_type, error_context) -> FailureClassification:
        prompt = CLASSIFY_FAILURE_PROMPT_TEMPLATE.format(
            failure_type=failure_type, error_context=error_context
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            return parse_classification_response(response.choices[0].message.content or "")
        except Exception as exc:
            logger.error("DeepSeekProvider.classify_failure failed: %s", exc)
            raise


# ── Together AI ─────────────────────────────────────────────────────────────


class TogetherProvider(PatchProvider):
    """Patch provider backed by Together AI via OpenAI-compatible API."""

    _DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    _BASE_URL = "https://api.together.xyz/v1"

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL):
        self._model_name = model
        if not api_key:
            raise RuntimeError("TogetherProvider requires a Together AI API key.")
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai package not installed — run: pip install openai")
        self.client = AsyncOpenAI(api_key=api_key, base_url=self._BASE_URL)

    def __repr__(self) -> str:
        return f"<TogetherProvider model={self._model_name!r}>"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_patch(
        self, old_api, new_api, code_snippet, context, defect_description="", observed_evidence=""
    ) -> str:
        prompt = PATCH_PROMPT_TEMPLATE.format(
            old_api=old_api or "(not applicable)",
            new_api=new_api or "(not applicable)",
            code_snippet=code_snippet,
            context=context,
            defect_description=defect_description or "Runtime defect detected.",
            observed_evidence=observed_evidence or "No additional evidence provided.",
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            return extract_diff(response.choices[0].message.content or "")
        except Exception as exc:
            logger.error("TogetherProvider.generate_patch failed: %s", exc)
            raise

    async def generate_patch_candidates(
        self,
        old_api,
        new_api,
        code_snippet,
        context,
        defect_description="",
        observed_evidence="",
        n=3,
    ) -> list[str]:
        return [
            await self.generate_patch(
                old_api, new_api, code_snippet, context, defect_description, observed_evidence
            )
            for _ in range(n)
        ]

    async def classify_failure(self, failure_type, error_context) -> FailureClassification:
        prompt = CLASSIFY_FAILURE_PROMPT_TEMPLATE.format(
            failure_type=failure_type, error_context=error_context
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            return parse_classification_response(response.choices[0].message.content or "")
        except Exception as exc:
            logger.error("TogetherProvider.classify_failure failed: %s", exc)
            raise


# ── Nvidia Nemotron ──────────────────────────────────────────────────────────


class NemotronProvider(PatchProvider):
    """Patch provider backed by Nvidia Nemotron via OpenAI-compatible API."""

    _DEFAULT_MODEL = "nvidia/llama-3.1-nemotron-70b-instruct"
    _BASE_URL = "https://integrate.api.nvidia.com/v1"

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL):
        self._model_name = model
        if not api_key:
            raise RuntimeError("NemotronProvider requires an Nvidia API key.")
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai package not installed — run: pip install openai")
        self.client = AsyncOpenAI(api_key=api_key, base_url=self._BASE_URL)

    def __repr__(self) -> str:
        return f"<NemotronProvider model={self._model_name!r}>"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_patch(
        self, old_api, new_api, code_snippet, context, defect_description="", observed_evidence=""
    ) -> str:
        prompt = PATCH_PROMPT_TEMPLATE.format(
            old_api=old_api or "(not applicable)",
            new_api=new_api or "(not applicable)",
            code_snippet=code_snippet,
            context=context,
            defect_description=defect_description or "Runtime defect detected.",
            observed_evidence=observed_evidence or "No additional evidence provided.",
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            return extract_diff(response.choices[0].message.content or "")
        except Exception as exc:
            logger.error("NemotronProvider.generate_patch failed: %s", exc)
            raise

    async def generate_patch_candidates(
        self,
        old_api,
        new_api,
        code_snippet,
        context,
        defect_description="",
        observed_evidence="",
        n=3,
    ) -> list[str]:
        return [
            await self.generate_patch(
                old_api, new_api, code_snippet, context, defect_description, observed_evidence
            )
            for _ in range(n)
        ]

    async def classify_failure(self, failure_type, error_context) -> FailureClassification:
        prompt = CLASSIFY_FAILURE_PROMPT_TEMPLATE.format(
            failure_type=failure_type, error_context=error_context
        )
        try:
            response = await self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            return parse_classification_response(response.choices[0].message.content or "")
        except Exception as exc:
            logger.error("NemotronProvider.classify_failure failed: %s", exc)
            raise
