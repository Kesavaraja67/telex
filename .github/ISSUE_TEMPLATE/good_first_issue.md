---
name: Good First Issue (Maintainer)
about: "For maintainers only: create a structured beginner-friendly issue"
title: "GFI-N — "
labels: ["good first issue"]
assignees: ""
---

<!--
This template is for MAINTAINERS creating beginner-friendly issues.
If you are a contributor looking to report a bug or suggest a feature,
please use the Bug Report or Feature Request templates instead.
-->

## Summary

<!-- One or two sentences describing the task in plain English. No jargon. -->

## Current Behavior

<!-- What does the code do right now? Be specific — name the file and function. -->

## Expected Behavior

<!-- What should it do after the fix? -->

## File(s) to Edit

<!-- List the exact file paths the contributor needs to change. -->

- `apps/...`

## How to Implement

<!-- 3–5 bullet points describing the change in plain English.
     If there is a pattern to follow elsewhere in the codebase, link it. -->

1.
2.
3.

## How to Test

<!-- What command should the contributor run to verify their change works? -->

```bash
# Example:
pytest apps/api/tests/test_github_service.py -v
npm run typecheck
```

## Acceptance Criteria

<!-- Checkboxes the contributor needs to satisfy before the PR is ready. -->

- [ ]
- [ ]
- [ ] All existing tests still pass (`pytest -v`)
- [ ] Lint passes (`ruff check .` and `black --check .`)

## Out of Scope

<!-- Explicitly list what contributors should NOT change in this issue. -->

- Do not modify unrelated files
- Do not change the database schema

## Resources

<!-- Links to relevant docs, code comments, or related PRs that help. -->

- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
