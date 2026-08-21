from typing import Literal, Protocol, TypedDict, runtime_checkable


class FailureClassification(TypedDict):
    classification: Literal["transient", "code_defect", "unknown"]
    reasoning: str
    recommended_action: str


@runtime_checkable
class PatchProvider(Protocol):
    """Interface every LLM patch provider must satisfy."""

    @property
    def model_name(self) -> str:
        ...

    async def generate_patch(
        self,
        old_api: str,
        new_api: str,
        code_snippet: str,
        context: str,
    ) -> str:
        """
        Generate a unified diff that migrates code_snippet from old_api to new_api.

        Returns:
            A unified diff string, or the literal string "UNABLE_TO_PATCH" if
            the provider cannot confidently generate a correct patch.
        """
        ...

    async def classify_failure(
        self,
        failure_type: str,
        error_context: str,
    ) -> FailureClassification:
        """
        Classify a runtime failure as transient or code_defect.

        Only called when the failure_type is NOT in the deterministic rule table
        in diagnose_runtime_failure.py (Tier 2 — genuinely ambiguous cases only).
        """
        ...

