# Telex — Demo & Reproduction Guide (15-Minute Evaluator Walkthrough)

This guide walks through evaluating Telex end-to-end:
1. **Scenario 1: Upstream Breaking Change Detection & Tree-Sitter AST Scanning (TypeScript & Python)**
2. **Scenario 2: Autonomous Patch Synthesis, Native CI Verification & Human-Reviewed GitHub PR Delivery**

---

## Live URLs
- **Telex Dashboard**: `http://localhost:3000` (or configured `WEB_APP_URL`)
- **Backend API**: `http://localhost:8000` (or configured `NEXT_PUBLIC_API_URL`)
- **API Health**: `http://localhost:8000/health`

---

## Scenario 1: Upstream Breaking Change Detection & AST Scanning

### Step 1: Upstream Registry Ingestion
When an upstream package (such as `openai` or `stripe`) publishes a breaking release on `npm` or `pypi`:
1. `poll_registry` discovers the new version and extracts changelog diffs.
2. `extract_changes` creates `DetectedChange` rows recording obsolete symbols, replacement APIs, and defect descriptions.

### Step 2: Multi-Language AST Repository Scanning
1. `scan_repo` inspects connected repositories for matching source files (`.ts`, `.tsx`, `.js`, `.py`).
2. Tree-Sitter queries execute natively against the AST:
   - TypeScript/JS: call expressions and member expressions.
   - Python: direct identifier calls and attribute method calls.
3. Every call site is isolated as a `CodeUsage` record with exact line and byte positions.

---

## Scenario 2: Autonomous Patch Synthesis & Verified GitHub PR

### Step 1: LLM Unified Diff Generation
1. `generate_patch` retrieves the target code snippet and context.
2. The active LLM provider (Gemini / Claude) synthesizes a minimal unified diff.
3. The diff is validated for format, bounds, and syntax correctness.

### Step 2: Native Sandbox Verification Gate
1. The patch is applied in an isolated clone sandbox.
2. The repository's configured gates (`requires_typecheck`, `requires_tests`) are enforced:
   - Typechecks (`tsc`, `mypy`) must pass cleanly.
   - Test suites (`pytest`, `npm test`) must exit with code 0.
3. If verification fails, a single bounded self-correction retry with compiler diagnostics is attempted.

### Step 3: Human-Reviewed Pull Request
1. Telex opens a pull request via the GitHub App with full disclosure of the verification mode (`full` or `structural_only`).
2. A human engineer reviews the pull request and merges it. **Telex never auto-merges.**

---

## Scenario 3: 3D Repo Atlas & Real-Time Incident Architecture Mapping

### Step 1: Navigating to Dedicated Repo Atlas
1. Open the **Telex Dashboard** at `http://localhost:3000/dashboard`.
2. Click **Repo Atlas** in the sidebar navigation (or browse directly to `/dashboard/atlas`).

### Step 2: Multi-Repository Switching
1. In the top navigation bar, use the **REPO:** dropdown to switch between any connected repositories (e.g. `Kesavaraja67/telex`, `Token-Print`, `aura-drops`).
2. The 3D layered scene initializes immediately, fetching the AST import graph, computing spatial coordinates, and caching the ready state.

### Step 3: Interactive Exploration & Breakage Inspection
1. **Camera Navigation**: Left-click and drag to orbit in 3D; mouse wheel to zoom; press <kbd>F</kbd> to re-center the panoramic perspective.
2. **Card Inspection**: Click on any file card to smoothly focus the camera and slide open the live Code Preview panel with syntax highlighting and last-edited commit metadata.
3. **Live Incident Overlays**: When a dependency incident breaks symbol usages, implicated files pulse in vivid rose (`#E11D48`), highlighting exactly which modules are impacted.

---

## Running Local Verification Tests

Telex includes 18 automated unit and integration tests across AST scanning and patch validation:

```bash
cd apps/api
pytest -v
```

Expected output:
```text
======================= 18 passed, 8 warnings in 3.50s =======================
```

To run the AST scanner suite specifically:
```bash
pytest tests/test_code_scanner.py -v
```

To run the patch generation & verification gate suite:
```bash
pytest tests/test_patch_generation.py -v
```
