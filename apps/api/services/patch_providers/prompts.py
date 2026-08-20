"""
Patch generation prompt template — Appendix A.
"""

PATCH_PROMPT_TEMPLATE = """You are generating a minimal code patch to fix a breaking API change.

OLD API:
{old_api}

NEW API:
{new_api}

CODE TO FIX:
{code_snippet}

SURROUNDING CONTEXT:
{context}

Return ONLY a unified diff that updates the code to use the new API.
Do not change anything unrelated to this specific API call.
Do not add comments explaining the change.
If you cannot confidently produce a correct patch, return exactly: UNABLE_TO_PATCH"""
