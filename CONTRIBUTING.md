<a id="top"></a>

<div align="center">

  <h1>Contributing to Telex</h1>
  <p><b>Guidelines for Engineering, Pull Requests, Code Style & Developer Onboarding</b></p>

  <p>
    <a href="https://github.com/psf/black">
      <img src="https://img.shields.io/badge/Code%20Style-Black-050508?style=flat-square" alt="Black" />
    </a>
    <a href="https://github.com/astral-sh/ruff">
      <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square" alt="Ruff" />
    </a>
    <img src="https://img.shields.io/badge/PRs-Welcome-14B8A6?style=flat-square" alt="PRs Welcome" />
  </p>

  <br>

  <p>
    <a href="#quickstart-zero-docker"><b>Zero-Docker Quickstart</b></a> &nbsp;•&nbsp;
    <a href="#quickstart-docker"><b>Docker Quickstart</b></a> &nbsp;•&nbsp;
    <a href="#seeded-demo"><b>Demo Data</b></a> &nbsp;•&nbsp;
    <a href="#telex-cli"><b>Standalone CLI</b></a> &nbsp;•&nbsp;
    <a href="#architecture"><b>Architecture</b></a> &nbsp;•&nbsp;
    <a href="#testing"><b>Testing Guide</b></a> &nbsp;•&nbsp;
    <a href="#standards"><b>Standards</b></a> &nbsp;•&nbsp;
    <a href="#checklist"><b>PR Checklist</b></a>
  </p>

</div>

> 🌱 **First time contributing to open source?** That's great — everyone starts
> somewhere! You don't need to understand the whole codebase. Pick an issue
> labeled [`good first issue`](https://github.com/Kesavaraja67/telex/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22),
> read only the files mentioned in that issue, make your change, and open a
> pull request. The maintainer will guide you through the rest in the PR
> comments. Questions are always welcome — just drop a comment on the issue.

<br>

---

<br>

## 01. Prerequisites

- **Python**: 3.10+ (tested on Python 3.10, 3.11, 3.12)
- **Node.js**: 18+ (`npm` 9+)
- **Git**
- **Docker & Docker Compose**: *Optional* (only required for full PostgreSQL + Redis containerized stack)

---

<br>

## <a id="quickstart-zero-docker"></a>02. Zero-Docker Quickstart (&lt; 5 Minutes)

You do **not** need Docker, PostgreSQL, Redis, or GitHub App secrets to develop Telex locally. Telex runs on local SQLite with zero external dependencies out of the box.

### One-Command Setup

**On Windows (PowerShell):**
```powershell
.\scripts\bootstrap.ps1
```

**On macOS / Linux (Bash):**
```bash
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

### What the bootstrap script does automatically:
1. Verifies your Python 3.10+ and Node 18+ environments.
2. Generates a local `.env` file with secure random session and encryption secrets.
3. Configures local SQLite (`sqlite+aiosqlite:///telex.db`) with zero Docker needed.
4. Installs Python dependencies and the standalone `telex-core` CLI package in editable mode.
5. Installs Next.js dependencies in `apps/web`.
6. Seeds 3 realistic demo repositories with breaking changes, patches, CI gate records, and pull requests via `scripts/seed_demo.py`.
7. Runs test verification to confirm your environment works.

### Launch Development Servers

```bash
# Terminal 1: Launch FastAPI backend (port 8000)
cd apps/api
uvicorn main:app --reload --port 8000

# Terminal 2: Launch Next.js dashboard (port 3000)
cd apps/web
npm run dev
```

Visit [`http://localhost:3000`](http://localhost:3000) to view the pre-populated dashboard!

---

<br>

## <a id="quickstart-docker"></a>03. Docker Quickstart (Full Production Stack)

To run the full stack with real PostgreSQL, Redis, and background worker jobs:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Launch PostgreSQL and Redis
docker compose up -d postgres redis

# 3. Install API dependencies and run database migrations
cd apps/api
pip install -r requirements.txt
alembic upgrade head

# 4. Start the background worker
python worker.py

# 5. Start API & Web servers
uvicorn main:app --reload --port 8000
npm --prefix ../web install && npm --prefix ../web run dev
```

---

<br>

## <a id="seeded-demo"></a>04. Seeded Demo Data

Telex provides an automated, idempotent demo seeder script to populate your local database with 3 realistic repositories:

```bash
# Seed demo data into SQLite
python scripts/seed_demo.py --sqlite

# Wipe and re-seed clean data
python scripts/seed_demo.py --sqlite --clean
```

### Seeded Repositories:
1. **`acme/web-app`** (TypeScript / Next.js):
   - Upstream dependency: `openai@3.3.0` → `4.0.0`
   - Breaking Change: `createCompletion` replaced by `chat.completions.create`
   - Outcome: Open PR #142 with full Jest test suite receipts
2. **`acme/data-pipeline`** (Python):
   - Upstream dependency: `pydantic@1.10.8` → `2.0.0`
   - Breaking Change: `BaseModel.dict()` renamed to `model_dump()`
   - Outcome: Merged PR #88 with pytest verification receipts
3. **`acme/api-gateway`** (JavaScript / Express):
   - Upstream dependency: `axios@0.27.2` → `1.6.0`
   - Breaking Change: `transformResponse` signature change (flagged as semantic risk)
   - Outcome: Open PR #57 marked with `[semantic-risk]` requiring human review

---

<br>

## <a id="telex-cli"></a>05. Standalone `telex` CLI

Telex includes a standalone, zero-infrastructure CLI engine in [`packages/telex-core`](packages/telex-core). You can use it anywhere locally:

```bash
# Install CLI
pip install -e packages/telex-core

# 1. Scan a local directory for call sites of a symbol:
telex scan ./src --package lodash --symbol get
telex scan ./services --package requests --symbol get --json

# 2. Analyze breaking changes between two package versions:
telex analyze lodash --from 4.17.20 --to 4.17.21 --ecosystem npm
telex analyze requests --from 2.25.0 --to 2.26.0 --ecosystem pypi

# 3. Test applying a unified diff (dry-run):
telex patch ./src/index.ts --diff ./patch.diff --dry-run

# 4. Verify local repository integrity:
telex verify ./src --test-cmd "pytest" --typecheck-cmd "mypy src"
```

---

<br>

## <a id="architecture"></a>06. Architecture in 5 Minutes

Telex operates as a six-stage automated pipeline:

```text
[Registry Watcher] (npm / PyPI)
        │
        ▼ (New Version Detected)
[Change Extractor] (Rule-based heuristics + LLM classifier)
        │
        ▼ (Breaking API Signatures Identified)
[Tree-Sitter Scanner] (TS/JS/Py import binding resolution)
        │
        ▼ (Exact Call Sites Isolated)
[Patch Generator] (Multi-provider LLM synthesis: Gemini, Claude, OpenAI)
        │
        ▼ (Candidate Unified Diff)
[Ephemeral CI Sandbox] (Real package tests + typechecks on dedicated runner)
        │
        ▼ (100% Green CI Gate Passed)
[Idempotent PR Creation] (1 PR per repo+version with verification receipts)
```

### Critical Pipeline Rules:
- **Zero Hallucinated Code**: Patches must pass the repository's real test suite on a dedicated verification branch before any pull request is opened.
- **Fail Closed**: If a patch fails to apply cleanly or base commit drifts, PR creation is aborted immediately. We never fall back to unmodified code.
- **Never Auto-Merge**: Telex opens ready-to-merge pull requests with verification evidence, but humans always retain ultimate merge authority.

---

<br>

## <a id="testing"></a>07. Testing Guide

Always run tests before opening a pull request:

```bash
# 1. Run backend tests (apps/api)
pytest -c apps/api/pyproject.toml apps/api

# 2. Run standalone CLI tests (packages/telex-core)
pytest packages/telex-core/tests

# 3. Test polyglot AST scanner, incremental atlas & run analysis
pytest apps/api/tests/test_code_scanner.py
pytest apps/api/tests/test_atlas_incremental.py
pytest apps/api/tests/test_repo_analysis.py

# 4. Run lint checks
ruff check .
black --check apps/api packages/telex-core

# 5. Run frontend typecheck & lint (apps/web)
cd apps/web
npm run typecheck
npm run lint
```

---

<br>

## <a id="standards"></a>08. Engineering Standards

1. **Python Code Style**:
   - Format with **Black** (100 characters max line length).
   - Lint with **Ruff** for imports and syntax.
2. **Simple English Comments**:
   - Write comments and docstrings in concise, plain English.
   - Explain *why* non-obvious code exists rather than restating what the code does.
3. **Security & Authorization**:
   - All repository-scoped routes must enforce `get_authorized_repo(session, repo_id, auth_data)`.
   - Never log or return unencrypted API keys or internal stack traces to clients.
4. **Git Discipline**:
   - Use conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
   - Never force-push (`git push --force`) to shared branches.

---

<br>

## <a id="issues"></a>09. Good First Issues & Issue Lifecycle

If you are a first-time contributor:
1. **Find an Issue**:
   - Look for issues labeled [`good first issue`](https://github.com/Kesavaraja67/telex/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) or [`help wanted`](https://github.com/Kesavaraja67/telex/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22).
   - Leave a comment saying: *"I would like to work on this issue!"*
2. **Create a Topic Branch**:
   ```bash
   git checkout -b feat/issue-<id>-short-name
   ```
3. **Link Your Pull Request**:
   - In your PR description, write: `Resolves #<id>` (e.g. `Resolves #32`).
   - When the PR is reviewed and merged, GitHub will automatically close the issue.

---

<br>

## <a id="checklist"></a>10. Pull Request Checklist

Before opening your pull request, verify:

- [ ] **Tests Added & Passing**: Verified with `pytest` across modified packages.
- [ ] **Lint Clean**: Passed `ruff check .` with zero errors.
- [ ] **Code Formatted**: Passed `black .` formatting.
- [ ] **Frontend Validation**: Passed `npm run typecheck` and `npm run lint` in `apps/web`.
- [ ] **Visual Proof**: UI changes include screenshots or screen recordings.
- [ ] **No Force Pushes**: Clean commit history.

---

<br>

## <a id="good-first-pr"></a>11. What Counts as a Good First PR?

You don't need to implement a whole feature. These are all perfectly valid first contributions:

| What | Example |
|---|---|
| **Fix a typo or improve a comment** | Rewrite a confusing inline comment in plain English |
| **Add a missing test** | Write one `pytest` test for an untested function |
| **Fix a small, well-scoped bug** | Fix a linting warning, a broken link, or a gitignore entry |
| **Improve a doc section** | Add an example command that's currently missing from the README |
| **Add an eslint-disable comment** | Suppress a false-positive linting warning with an explanation |

> The bar for a first PR is: **does it make the repo a little better, without breaking anything?** That's it.

---

<br>

## <a id="common-mistakes"></a>12. Common Mistakes to Avoid

These are the things maintainers most often have to ask contributors to fix:

1. **Force-pushing after opening a PR** (`git push --force`) — this rewrites history
   and breaks the review thread. Always use `git push` (without `--force`) after a PR is open.

2. **Making unrelated changes in the same PR** — if you're fixing a bug in
   `github_service.py`, don't also reformat an unrelated file at the same time.
   One PR = one purpose.

3. **Skipping tests** — every change to Python logic needs a matching `pytest`
   test. If you're not sure what to test, add a comment in the PR and the
   maintainer will help.

4. **Committing environment files or secrets** — never commit `.env`, API keys,
   or personal tokens. The `.gitignore` already excludes these, but double-check
   with `git status` before committing.

5. **Opening a huge PR without prior discussion** — if your change touches more
   than ~5 files or rewrites a major component, open an issue first to discuss
   the approach. This avoids wasted effort if the direction changes.

<br>

<div align="center">
  <a href="#top">
    <img src="https://img.shields.io/badge/%E2%86%91-Back%20to%20Top-050508?style=flat-square&logoColor=white" alt="Back to Top" />
  </a>
</div>

