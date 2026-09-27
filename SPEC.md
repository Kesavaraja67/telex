# TELEX EXECUTABLE SPECIFICATION (PHASES 1–8)

**Status**: Approved Specification  
**Baseline Anchor**: [Phase -1 Baseline Report](phase_minus_1_baseline_report.md) (commit `4719337`)  
**Target System**: Telex Autonomous Self-Healing Dependency Bot  

---

## 1. System Invariants & Source-of-Truth Rules

1. **Reality Precedes Claims**: No feature, ecosystem, language, or metric is documented or exposed in API responses without working code and passing tests.
2. **Fail Closed**: Any security check, OAuth validation, verification gate, or patch application failure MUST fail closed (reject access, abort workflow, mark unverified, or refuse PR creation).
3. **Evidence-Bound Verification**: `verified == true` is strictly reserved for candidate patches that passed the designated Telex verification workflow on GitHub Actions on the exact commit SHA being patched.
4. **Tenant Isolation**: Every repository resource and action requires authentication AND proof that the caller is entitled to access the target repository's installation.
5. **Deterministic Pipeline**: Data produced in upstream pipeline stages (ecosystem, changelog, version numbers, commit SHAs) must never be dropped or replaced with sentinel strings (`"unknown"`) in downstream handlers.

---

## 2. Data Contracts & Pipeline Topology

The automated self-healing pipeline follows a strict, type-safe data contract through 6 sequential stages:

```
[Registry Polling]
       │  (ecosystem, package_id, version, published_at, changelog_url/raw, old_version)
       ▼
[Change Extraction]
       │  (package_version_id, detected_change_ids, change_type, symbol_old, symbol_new, confidence)
       ▼
[Repository Scanning]
       │  (repo_id, detected_change_id, file_path, line_start, line_end, byte_offsets, import_binding)
       ▼
[Patch Synthesis]
       │  (code_usage_id, unified_diff, provider, model)
       ▼
[Sandboxed Verification]
       │  (patch_id, base_sha, verification_commit_sha, telex_check_conclusion, verification_mode)
       ▼
[Idempotent PR Creation]
          (repo_id, package_version_id, idempotency_key, github_pr_url)
```

### Stage 1: Registry Polling (`jobs/handlers/poll_registry.py`)
- **Input Contract**:
  ```json
  {
    "package_id": "UUID",
    "package_name": "str",
    "ecosystem": "npm | pypi"
  }
  ```
- **Execution Invariants**:
  1. Dispatch to registry watcher via `ecosystem`:
     - `npm` → `https://registry.npmjs.org/<package>`
     - `pypi` → `https://pypi.org/pypi/<package>/json`
     - unsupported → Log warning, record failure, do not default to npm.
  2. Query `PackageVersion` for the highest existing known version before inserting the new version:
     - If prior versions exist: `old_version = previous_known_version`
     - If no prior versions exist: `old_version = None` (initial package discovery, skip extraction or record baseline)
  3. Extract `changelog_url` and raw changelog content where available.
  4. Persist `PackageVersion`:
     - `package_id`, `version`, `published_at`, `changelog_raw`.
  5. Enqueue `extract_changes` with explicit payload:
     ```json
     {
       "package_version_id": "<uuid>",
       "package_name": "<name>",
       "ecosystem": "<ecosystem>",
       "old_version": "<old_version>",
       "new_version": "<new_version>",
       "changelog": "<raw_changelog_text>"
     }
     ```

### Stage 2: Change Extraction (`jobs/handlers/extract_changes.py`)
- **Input Contract**:
  Requires `package_version_id`, `package_name`, `new_version`. Reads `changelog` and `old_version`.
- **Validation Schema (Pydantic)**:
  ```python
  class ExtractedChangeSchema(BaseModel):
      change_type: Literal["signature_change", "removed", "renamed", "deprecated", "behavior_change"]
      symbol_old: Field(str, min_length=1, max_length=256)
      symbol_new: Optional[Field(str, max_length=256)] = None
      description: Field(str, min_length=5, max_length=1000)
      confidence: Field(float, ge=0.0, le=1.0)
  ```
- **Bounds**:
  - Max changelog input: 8,000 characters.
  - Max extracted changes per release: 25 changes.
  - LLM response must strictly parse against `list[ExtractedChangeSchema]`.
- **Non-LLM Structural Signal**:
  - Compare exported API symbol sets between previous and new package versions (AST or package export introspection).
  - Add structural diff evidence to supplement LLM changelog parsing.
- **Output**:
  Persist `DetectedChange` rows. Record `IncidentEvent(event_type="change_detected")`. Enqueue `scan_repo` for all repositories tracking this package.

### Stage 3: Repository Scanning (`jobs/handlers/scan_repo.py` & `telex-core`)
- **Input Contract**:
  ```json
  {
    "repo_id": "UUID",
    "package_version_id": "UUID"
  }
  ```
- **Language Scope**:
  - **Supported**: TypeScript (`.ts`, `.mts`, `.cts`), TSX (`.tsx`), JavaScript (`.js`, `.jsx`, `.mjs`, `.cjs`), Python (`.py`).
  - All other extensions are skipped.
- **Dependency & Namespace Resolution**:
  - Tree-sitter AST queries must resolve import statements:
    - `import { foo } from 'lib'` → bind `foo` to target package.
    - `import * as lib from 'lib'` → bind `lib.*` member expressions.
    - `from lib import foo` (Python) → bind `foo` calls.
    - `import lib` (Python) → bind `lib.foo()` calls.
  - Unrelated identifiers matching `symbol_old` from other libraries or local functions MUST NOT produce a `CodeUsage`.
- **Output**:
  Insert `CodeUsage` rows. Enqueue `generate_patch` for each new usage.

### Stage 4: Patch Synthesis (`jobs/handlers/generate_patch.py`)
- **Input Contract**:
  ```json
  { "code_usage_id": "UUID" }
  ```
- **Execution Invariants**:
  - Generate unified diff modifying only the targeted call site.
  - Validate patch format: must parse as unified diff, apply cleanly to snippet in memory, and not alter out-of-scope code.
  - Insert `Patch` row (`verified=False`).
  - Enqueue `validate_patch`.

### Stage 5: Verification Gate (`jobs/handlers/validate_patch.py`)
- **Input Contract**:
  ```json
  { "patch_id": "UUID" }
  ```
- **Execution Invariants**:
  1. Resolve `base_sha` from target repo default branch.
  2. Apply diff in-memory to target file. If git apply fails → Fail closed immediately, record `ValidationRun(applies_cleanly=False, verified=False)`.
  3. Inspect environment:
     - Node: inspect `package.json` scripts, lockfile, tsconfig.
     - Python: inspect `requirements.txt`/`pyproject.toml`, check whether pytest or unittest is configured. Do NOT assume pytest exists.
  4. Create isolated verification branch: `telex/validate-<patch_id_hex>`.
  5. Atomically commit verification bundle: patched file + dynamic verification workflow `.github/workflows/telex-verify.yml`.
  6. Capture `verification_commit_sha`.
  7. Poll GitHub check runs:
     - ONLY observe check runs matching `telex-verify` or `expected_workflow_name`.
     - NEVER fall back to unrelated repository check runs.
     - Conclusions:
       - `success` → eligible as passing evidence.
       - `failure`, `cancelled`, `timed_out` → failed verification.
       - `skipped`, `neutral` → NOT evidence of passed tests; fails verification.
  8. Delete verification branch.
  9. Persist `ValidationRun`:
     - Save `patch_id`, `verification_mode`, `base_sha`, `commit_sha`, `workflow_name`, `applies_cleanly`, `parses`, `typechecks`, `tests_pass`, `scope_ok`, `log`.
  10. Set `patch.verified = True` ONLY if all required repo gates pass on the exact verification commit.
  11. If verified, trigger/coordinate PR creation.

### Stage 6: Idempotent PR Creation (`jobs/handlers/open_pr.py`)
- **Unit of Work**:
  **One PR per repository + dependency-version repair event.**
- **Pre-Flight Invariants**:
  1. Query all verified patches for `(repo_id, package_version_id)`.
  2. Verify repository base commit has not drifted:
     - If default branch HEAD != `base_sha` used in validation:
       - Mark verification stale.
       - Re-evaluate / revalidate patches against new base SHA.
       - Do NOT open PR on stale base.
  3. Apply all patches to target files.
     - If ANY patch fails to apply: FAIL CLOSED.
     - Do NOT use original file as fallback.
     - Abort PR creation; record `IncidentEvent(event_type="patch_failed")`.
  4. Enforce idempotency:
     - Check if an open PR already exists for `(repo_id, package_version_id)`.
     - If an open PR exists: update existing PR branch or log and skip. Do NOT open duplicate PR.
  5. Open PR, record `PullRequest` row with `patch_ids`, emit `pr_opened` event.

---

## 3. Security & Authorization Invariants

1. **Repository Authorization Primitive**:
   All repository-scoped routes (`GET /api/repos/{repo_id}`, `POST /api/repos/{repo_id}/toggle`, `PATCH /api/repos/{repo_id}`, `GET /api/repos/{repo_id}/patches`, `POST /api/repos/{repo_id}/ai-explain`, `GET /api/repos/{repo_id}/atlas/*`) MUST call `get_authorized_repo(session, repo_id, auth_data)`.
   - Unauthorized user → HTTP 403 Forbidden.
   - Nonexistent repository → HTTP 404 Not Found.
   - Unauthenticated user → HTTP 401 Unauthorized.
2. **Abuse & Cost Controls on Trigger Routes**:
   - `POST /api/repos/{repo_id}/ai-explain`: Requires authenticated caller with authorized repo access. Rate-limited.
   - `POST /api/packages/{package_id}/rescan`: Requires authenticated user. Enforces duplicate rescan debounce (cannot re-enqueue if a scan job is already queued or active for that version).
3. **Fail-Closed OAuth State Validation**:
   - `stored_nonce = request.cookies.get("telex_oauth_state", "")`
   - `nonce_from_state = parts[0] if parts else ""`
   - Validation invariant:
     ```python
     if not stored_nonce or not nonce_from_state or not secrets.compare_digest(stored_nonce, nonce_from_state):
         raise HTTPException(status_code=400, detail="Invalid or missing OAuth state")
     ```
   - Missing state on either side MUST raise HTTP 400.
4. **Sanitized Error Responses**:
   - Global exception handler in `main.py` returns `{"detail": "Internal server error"}` with HTTP 500.
   - Raw exception details (`str(exc)`) are logged server-side only; never leaked in API JSON responses.
5. **CORS & Cookie Safety**:
   - Production requires explicit allowed origin domain matching.
   - Session cookies use `HttpOnly=True`, `Secure=True`, and `SameSite="lax"` (or tightly scoped `"none"` exclusively for trusted cross-domain frontends).

---

## 4. Standalone `telex-core` Architecture & Boundaries

`telex-core` is a zero-dependency (no database, no GitHub App, no LLM provider) Python package for AST scanning:

- **Directory**: `packages/telex-core` or `apps/api/core`
- **CLI Command**:
  ```bash
  telex scan <path-to-repo> [--package <name>] [--symbol <name>]
  ```
- **Included Capabilities**:
  - File walker respecting `.gitignore` and max file size limits.
  - Language detection from extensions (`.ts`, `.tsx`, `.js`, `.py`).
  - Tree-sitter grammar loading and query execution.
  - Import tracking and call-site extraction.
  - JSON and human-readable terminal output.
- **Platform Sharing**:
  `apps/api/services/code_scanner.py` directly imports and uses the `telex-core` scanner engine. Zero divergence between CLI and cloud platform.

---

## 5. Domain Metrics & Product Funnel Instrumentation

All analytics and dashboard statistics must map 1:1 to real database events:

| Metric Name | Database Ground Truth | Current Code Flaw Fixed |
|---|---|---|
| `repos_watched` | `SELECT count(*) FROM repos WHERE is_active=True` | Accurately scoped to tenant |
| `breaking_changes_detected` | `SELECT count(*) FROM detected_changes` | Real count of extracted changes |
| `call_sites_found` | `SELECT count(*) FROM code_usages` | Exact AST usage count |
| `patches_generated` | `SELECT count(*) FROM patches` | **Fixed**: Previously queried `WHERE verified=True` |
| `patches_verified` | `SELECT count(*) FROM patches WHERE verified=True` | Explicit separate metric |
| `prs_opened` | `SELECT count(*) FROM pull_requests` | Real count of opened PRs |
| `prs_merged` | `SELECT count(*) FROM pull_requests WHERE status='merged'` | Real merged PRs |
| `merge_rate` | `prs_merged / prs_opened` (if prs_opened > 0) | Real percentage |

---

## 6. Execution Acceptance Criteria

- [x] Every API endpoint touching a repository requires authentication and checks authorization.
- [x] OAuth callback rejects missing, empty, or mismatched state parameters with HTTP 400.
- [x] HTTP 500 responses do not contain internal exception messages or stack traces.
- [x] Automatic registry polling passes real ecosystem, changelog text, and old/new version numbers to extraction.
- [x] LLM extraction output is strictly validated against a bounded Pydantic schema.
- [x] AST scanner matches symbols only when imported from the target package.
- [x] Verification fails closed when Telex verification workflow is missing, skipped, or neutral.
- [x] Validated patches store base SHA and verification commit SHA.
- [x] Repository drift between validation and PR creation triggers rebase/revalidation.
- [x] Patch application failure fails closed without opening PR.
- [x] PR creation is idempotent: 1 PR per dependency repair event.
- [x] Standalone `telex scan` CLI runs in < 2 seconds with zero external services.
- [x] All present-tense README claims match code reality.

---

## 7. Phase 12 Specification: Multi-Language & Multi-Ecosystem Scale

**Objective**: Scale Telex from npm and PyPI to all major modern software ecosystems (Go, Rust, Java, Ruby, C#/.NET) while maintaining strict semantic guarantees, Tree-sitter AST call-site precision, and fail-closed isolated sandbox verification.

### 7.1 Architecture & Ecosystem Abstraction Matrix

Every supported ecosystem implements three decoupled interfaces:
1. `RegistryWatcher`: Dispatches to upstream package indexes to detect new versions and raw release notes.
2. `ASTScanner`: Tree-sitter query engine resolving exact symbol import bindings, aliases, and call sites.
3. `SandboxEnvironment`: Generates native isolated verification workflows with scripts blocked by default.

| Ecosystem | Package Registry | Manifest Files | Tree-sitter Grammar | Native Verification Command | Lifecycle Script Defense |
|---|---|---|---|---|---|
| **JavaScript / TS** | npm (`registry.npmjs.org`) | `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock` | `tree-sitter-typescript`, `tree-sitter-javascript` | `npm test` / `pnpm test` / `yarn test` | `--ignore-scripts` by default |
| **Python** | PyPI (`pypi.org/pypi/<pkg>/json`) | `requirements.txt`, `pyproject.toml`, `Pipfile`, `poetry.lock` | `tree-sitter-python` | `pytest` / `python -m unittest` | Dependency install skipped unless opt-in |
| **Go** | Go Proxy (`proxy.golang.org`) | `go.mod`, `go.sum` | `tree-sitter-go` | `go test ./...` | Strict module hash verification (`go.sum`) |
| **Rust** | Crates.io (`crates.io/api/v1/crates`) | `Cargo.toml`, `Cargo.lock` | `tree-sitter-rust` | `cargo test --workspace` | Offline/locked build flags (`--locked`) |
| **Java / JVM** | Maven Central (`repo1.maven.org`) | `pom.xml`, `build.gradle`, `build.gradle.kts` | `tree-sitter-java` | `mvn test` / `./gradlew test` | Sandboxed dependency resolution |
| **Ruby** | RubyGems (`rubygems.org/api/v1`) | `Gemfile`, `Gemfile.lock` | `tree-sitter-ruby` | `bundle exec rspec` / `rake test` | Frozen lockfile enforcement |
| **C# / .NET** | NuGet (`api.nuget.org/v3/index.json`) | `*.csproj`, `Directory.Packages.props`, `packages.lock.json` | `tree-sitter-c-sharp` | `dotnet test --no-restore` | Locked restore mode (`--locked-mode`) |

### 7.2 Tree-sitter AST Import Binding Contracts (Across All Languages)

For every new language added in Phase 12, the scanner MUST resolve import bindings to the specific target package before flagging call sites:
- **Go**: Distinguish local package functions from external imported module functions (e.g. `import "github.com/gin-gonic/gin"` -> `gin.Default()`).
- **Rust**: Resolve `use crate::*` vs `use external_crate::*`, renamed imports (`use serde::Deserialize as De`), and fully-qualified calls (`tokio::spawn`).
- **Java**: Match package declarations, wildcard imports (`import org.slf4j.*`), and static method imports.
- **Ruby**: Match `require` statements and module namespace scoping (`Stripe::Charge.create`).
- **C#**: Match `using Namespace;` directives, static using (`using static Math;`), and namespace aliasing.

### 7.3 Multi-Language Verification Pipeline Contracts

1. **Deterministic Environment Probing**:
   - `detect_repo_environment` inspects repository file manifests in deterministic priority order.
   - If multiple language manifests exist (monorepo or polyglot), Telex generates matrix jobs targeting only the subdirectories affected by the dependency change.
2. **Fail-Closed Patch Application**:
   - Patches are synthesized as unified diffs and validated using `git apply --check`.
   - If any whitespace, AST syntax error, or compile failure occurs, the patch is marked `verification_passed=False` and no PR is opened.

