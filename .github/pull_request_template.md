<!--
👋 First-time contributor? Welcome! Here's what to do:
  1. Fill in the Description and Related Issue below.
  2. Check off the items in the Quality Checklist that apply to your change.
  3. If you're unsure about anything, just leave a comment — the maintainer
     will help you through the review.
  You don't need to fill in every section perfectly on the first try.
-->

## Description
<!-- Provide a brief description of the changes introduced by this pull request. -->

## Related Issue
<!-- Link the issue this PR resolves, e.g. Fixes #123 or Closes #456 -->
Fixes #


## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code style / formatting / refactor (no logic change)
- [ ] Tests (adding or updating test cases)

---

## Visual Evidence (Mandatory for UI / UX / Dashboard Changes)
<!--
IMPORTANT: If your pull request introduces, updates, or fixes any user interface, visual layout,
dashboard component, styling, or frontend workflow, you MUST attach visual evidence below.
Accepted formats:
- Screenshots (PNG/JPG) showing Before and After states.
- Screen recording (GIF/MP4/WebM) demonstrating the interaction flow.
-->

### Before
<!-- Insert screenshot or recording of the previous state, or N/A -->

### After
<!-- Insert screenshot or recording of the new state -->

---

## Test Coverage & Verification
<!-- Confirm that appropriate tests were written and coverage exceeds 80% -->
- [ ] **Appropriate Tests**: Wrote comprehensive unit/integration tests for all added or modified logic.
- [ ] **Coverage Above 80%**: Ran backend tests locally; coverage strictly exceeds **80%** (`pytest --cov=. --cov-fail-under=80`).

---

## Quality & Contribution Checklist
- [ ] **Issue Linked / Scoped**: For larger feature work, the relevant issue is referenced (small fixes, typos, or documentation do not require an issue).
- [ ] **No Force Pushes or Rebasing**: I have **NOT** force pushed (`git push --force`) or rebased this PR branch after opening it.
- [ ] **Professional Conversation Only**: All communications in this PR, commits, and discussions are polite, constructive, and professional.
- [ ] **Simple English Comments**: All code comments and docstrings are written strictly in **simple, plain English**.
- [ ] **Python Formatting & Linting**: Code passes `black .` formatting and `ruff check --fix .` linting in `apps/api`.
- [ ] **Frontend Validation**: Ran `npx tsc --noEmit` and `npm run lint` in `apps/web` with zero errors.
- [ ] **No Secrets Committed**: Verified that no secrets, credentials, or production tokens are exposed.
- [ ] **Clean Commits**: Commit messages follow Conventional Commits standard (`feat:`, `fix:`, `docs:`).
