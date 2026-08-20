from typing import Protocol, runtime_checkable


@runtime_checkable
class PatchProvider(Protocol):
    """Interface every LLM patch provider must satisfy."""

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
