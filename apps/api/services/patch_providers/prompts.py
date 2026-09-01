"""
Prompt templates — Appendix A.
"""

PATCH_PROMPT_TEMPLATE = """You are repairing a confirmed runtime software defect.

DEFECT DESCRIPTION:
{defect_description}

OBSERVED EVIDENCE:
{observed_evidence}

FILE UNDER REPAIR:
{context}

CURRENT SOURCE CODE:
{code_snippet}

ADDITIONAL CONTEXT:
Old symbol: {old_api}
New symbol: {new_api}

Generate the smallest correct unified diff that fixes the described defect.

Requirements:
- Change ONLY the code necessary to fix the described defect.
- Preserve all existing behavior unrelated to the defect.
- The diff MUST apply cleanly to the source shown above.
- Return ONLY a valid unified diff (--- / +++ / @@ headers included).
- Do NOT add comments explaining the change.
- Do NOT invent new APIs, files, or functions.
- Do NOT rewrite unrelated code.
- If you cannot confidently produce a correct minimal patch, return exactly: UNABLE_TO_PATCH"""


CLASSIFY_FAILURE_PROMPT_TEMPLATE = """You are classifying a runtime payment failure to determine whether it requires a code fix or just a retry.

FAILURE TYPE: {failure_type}

ERROR CONTEXT:
{error_context}

IMPORTANT: This failure type was NOT found in the deterministic classification rule table.
You are being asked precisely because this is an ambiguous case that the rule table cannot resolve.
Apply careful judgment — do not default to "transient" unless the evidence clearly supports it.

Classify this failure as one of:
- "transient": A temporary infrastructure or network condition that will likely resolve on its own.
  Examples: momentary network blips, rate limits, temporary service unavailability.
- "code_defect": A bug in our own payment handling code that will recur on retry.
  Examples: incorrect request structure, missing required fields, logic errors in webhook handling.
- "unknown": The failure cause cannot be confidently determined from the provided context.

Respond in this exact JSON format (no markdown, no extra text):
{{
  "classification": "transient", "code_defect", or "unknown",
  "reasoning": "one or two sentences explaining why",
  "recommended_action": "what should happen next (retry / open PR / investigate)"
}}

If you genuinely cannot determine the classification from the available information, use "unknown" and explain why in reasoning."""

