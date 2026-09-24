<a id="top"></a>

<div align="center">

  <h1>Telex Evaluator Guide</h1>
  <p><b>15-Minute Interactive Demonstration & Autonomous Reproduction Walkthrough</b></p>

  <p>
    <img src="https://img.shields.io/badge/Duration-15%20Minutes-050508?style=flat-square" alt="Duration: 15 Mins" />
    <img src="https://img.shields.io/badge/Walkthrough-3%20Core%20Scenarios-14B8A6?style=flat-square" alt="3 Scenarios" />
    <img src="https://img.shields.io/badge/Tests-Passing-10B981?style=flat-square&logo=pytest&logoColor=white" alt="Tests Passing" />
    <img src="https://img.shields.io/badge/Review-Human%20in%20the%20Loop-F43F5E?style=flat-square" alt="Human in the Loop" />
  </p>

  <br>

  <p>
    <a href="#live-endpoints"><b>Endpoints</b></a> &nbsp;•&nbsp;
    <a href="#scenario-1"><b>Scenario 1: AST Scan</b></a> &nbsp;•&nbsp;
    <a href="#scenario-2"><b>Scenario 2: LLM Patch</b></a> &nbsp;•&nbsp;
    <a href="#scenario-3"><b>Scenario 3: 3D Repo Atlas</b></a> &nbsp;•&nbsp;
    <a href="#automated-tests"><b>Test Verification</b></a>
  </p>

</div>

<br>

---

<br>

## <a id="live-endpoints"></a>01. Live Local Endpoints

Before beginning, ensure local services are running per the [Quickstart](README.md#local-setup):

| Interface | URL | Purpose |
|---|---|---|
| **Operator Cockpit** | `http://localhost:3000/dashboard` | Main telemetry overview, repo fleet & activity feed |
| **3D Repo Atlas** | `http://localhost:3000/dashboard/atlas` | Interactive 3D spatial visualizer & blast radius viewer |
| **Backend REST API** | `http://localhost:8000` | FastAPI application endpoints |
| **Health Probe** | `http://localhost:8000/health` | Service health status and active LLM provider |
| **Interactive API Docs** | `http://localhost:8000/docs` | Swagger UI with OpenAPI specification |

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="scenario-1"></a>02. Scenario 1: Upstream Breaking Change Detection & AST Scanning

This scenario demonstrates how Telex intercepts upstream library releases and isolates code call sites using Tree-Sitter syntax analysis.

### Step 1: Upstream Registry Ingestion
When an upstream library (e.g. `openai`, `stripe`, `axios`) publishes a breaking release on `npm` or `PyPI`:
1. `poll_registry` discovers the new version and downloads release notes.
2. `extract_changes` analyzes changelog diffs using LLMs to structure obsolete symbols, replacement APIs, and defect descriptions into structured database records.

### Step 2: Multi-Language AST Repository Scanning
1. `scan_repo` inspects connected repositories for matching source files (`.ts`, `.tsx`, `.js`, `.py`).
2. Tree-Sitter queries execute natively against the AST:
   - TypeScript/JS: call expressions and member expressions.
   - Python: direct identifier calls and attribute method calls.
3. Every call site is isolated as a `CodeUsage` record with exact line and byte positions.
4. **Zero Regex Noise**: Comments, markdown documentation, and string literals matching the symbol name are completely ignored.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="scenario-2"></a>03. Scenario 2: Autonomous Patch Synthesis & Native CI Verification

This scenario demonstrates candidate patch generation, structural validation, and ephemeral CI testing.

### Step 1: LLM Unified Diff Generation
1. `generate_patch` retrieves the target code snippet, obsolete symbol, and replacement documentation.
2. The active LLM provider (Gemini 2.5 Flash / Claude / OpenAI) synthesizes a surgical unified diff targeting only the broken call site.
3. Up to 3 candidate patches are evaluated; the engine verifies `git apply --check` and selects the smallest valid diff.

### Step 2: Native Sandbox CI Verification Gate
1. The patch is applied inside an isolated sandbox clone of the target repository.
2. Configured verification gates are strictly enforced:
   - Typechecks (`tsc`, `mypy`) must pass cleanly.
   - Test suites (`pytest`, `npm test`) must exit with code 0.
3. If tests fail, a single bounded self-correction retry with compiler diagnostics is attempted.

### Step 3: Human-Reviewed Pull Request
1. Telex opens a pull request via the GitHub App with full disclosure of the verification mode (`full` or `structural_only`).
2. A human engineer reviews the pull request and merges it. **Telex never auto-merges.**

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="scenario-3"></a>04. Scenario 3: 3D Repo Atlas & Real-Time Incident Mapping

Experience the 3D architectural visualizer and blast radius intelligence engine.

### Step 1: Navigating to Dedicated Repo Atlas
1. Open the **Telex Dashboard** at `http://localhost:3000/dashboard`.
2. Click **Repo Atlas** in the sidebar navigation (or browse directly to `/dashboard/atlas`).

<br>

<div align="center">
  <img src="apps/web/public/repo-atlas-overview.png" alt="Telex Repo Atlas - 3D Overview" width="100%" style="border-radius: 8px; border: 1px solid rgba(255,255,255,0.12);" />
</div>

<br>

### Step 2: Multi-Repository Switching
1. In the top navigation bar, use the **REPO:** dropdown to switch between connected repositories (e.g. `Kesavaraja67/telex`, `Token-Print`, `aura-drops`).
2. The 3D layered scene initializes immediately, fetching the AST import graph, computing spatial coordinates, and caching the ready state.

### Step 3: Camera Controls & Keybindings
| Action | Keybinding / Gesture |
|---|---|
| **Orbit Camera** | Left-click + drag on canvas |
| **Pan Camera** | Right-click + drag (or Shift + left-click drag) |
| **Zoom View** | Mouse wheel scroll (or two-finger trackpad pinch) |
| **Center / Reset Camera** | Press <kbd>F</kbd> key |
| **Toggle Legend** | Press <kbd>L</kbd> key |
| **Force Refresh Graph** | Press <kbd>R</kbd> key |

### Step 4: In-Canvas Card Inspection
1. Click on any 3D file card to smoothly focus the camera and slide open the live Code Preview panel.
2. Review syntax-highlighted source code, call sites, and Git commit metadata.

<br>

<div align="center">
  <img src="apps/web/public/repo-atlas-inspect.png" alt="Telex Repo Atlas - Code Inspection" width="100%" style="border-radius: 8px; border: 1px solid rgba(255,255,255,0.12);" />
</div>

<br>

### Step 5: Visualizing the Package Break Blast Radius
- When an upstream package breaks, developers don't have to guess or grep. Repo Atlas illuminates the entire failure propagation path across module boundaries in 3D.
- Implicated cards and severed conduits switch to vivid crimson (`#F43F5E`) via real-time SSE streams (`/api/repos/{id}/incidents/stream`).
- Operators can trace connected wires and read code directly inside the 3D canvas to verify that the LLM's fix targets only the affected call sites without collateral breakage.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="automated-tests"></a>05. Running Local Automated Tests

Run the full backend test suite:
```bash
cd apps/api
pytest -v
```

Expected output:
```text
tests/test_code_scanner.py ............. PASSED
tests/test_patch_generation.py ......... PASSED
tests/test_github_service.py ........... PASSED
tests/test_queue.py .................... PASSED
tests/test_routers_stats.py ............ PASSED

======================= all test suites passed =======================
```

To run individual suites:
```bash
# Tree-Sitter AST Scanner
pytest tests/test_code_scanner.py -v

# Patch Generation & Verification Gate
pytest tests/test_patch_generation.py -v

# Telemetry & Stats Router
pytest tests/test_routers_stats.py -v
```

<br>

<div align="center">
  <a href="#top">
    <img src="https://img.shields.io/badge/%E2%86%91-Back%20to%20Top-050508?style=flat-square&logoColor=white" alt="Back to Top" />
  </a>
</div>
