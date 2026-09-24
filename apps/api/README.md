<a id="top"></a>

<div align="center">

  <h1>Telex API Substrate</h1>
  <p><b>FastAPI REST Service, PostgreSQL Job Queue & Autonomous Code Repair Substrate</b></p>

  <p>
    <a href="https://github.com/astral-sh/ruff">
      <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square" alt="Ruff" />
    </a>
    <a href="https://github.com/psf/black">
      <img src="https://img.shields.io/badge/Code%20Style-Black-050508?style=flat-square" alt="Code Style: Black" />
    </a>
    <img src="https://img.shields.io/badge/Coverage-%E2%89%A580%25-10B981?style=flat-square&logo=pytest&logoColor=white" alt="Test Coverage" />
    <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
    <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  </p>

  <br>

  <p>
    <a href="#overview"><b>Overview</b></a> &nbsp;•&nbsp;
    <a href="#architecture--modules"><b>Modules</b></a> &nbsp;•&nbsp;
    <a href="#endpoint-catalog"><b>Endpoints</b></a> &nbsp;•&nbsp;
    <a href="#job-queue"><b>Queue Architecture</b></a> &nbsp;•&nbsp;
    <a href="#tree-sitter-ast"><b>Tree-Sitter Scanner</b></a> &nbsp;•&nbsp;
    <a href="#local-setup"><b>Setup</b></a> &nbsp;•&nbsp;
    <a href="#testing"><b>Testing</b></a>
  </p>

</div>

<br>

---

<br>

## <a id="overview"></a>01. Overview

The `apps/api` service is Telex's core autonomous runtime. It handles:
- **Registry Polling**: Monitors npm and PyPI package indices around the clock for breaking releases and changelogs.
- **Tree-Sitter AST Analysis**: Inspects repository source trees to locate affected function signatures, member expressions, and call sites with zero regex false positives.
- **3D Repo Atlas Cartography**: Computes hierarchical folder depth, polar force coordinates, and real-time SSE incident streams for `/dashboard/atlas`.
- **LLM Patch Generation**: Prompts 10 supported LLM providers for surgical unified diffs.
- **Ephemeral Sandbox Verification**: Clones repositories into isolated workspaces, executes your real test suites, and typechecks before delivering pull requests.
- **PostgreSQL SKIP LOCKED Queue**: Guarantees atomic, crash-resilient task processing with per-tenant fairness caps.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="architecture--modules"></a>02. Key Modules & Subsystems

| Module | Location | Purpose & Engineering Guarantees |
|---|---|---|
| **Auth Router** | `routers/auth.py` | GitHub OAuth callback exchange, JWT session signing, and `/api/auth/me` with secure HttpOnly cookies. |
| **Repo Router** | `routers/repos.py` | Repository synchronization, tracking status toggles, and CI gate configurations (`requires_tests`, `requires_typecheck`). |
| **Atlas Router** | `routers/atlas.py` | 3D AST import graph generation, on-demand code preview with line bounds, and file commit history. |
| **Incidents Stream** | `routers/atlas.py` | Real-time Server-Sent Events (SSE) broadcasting live incident blast radius pulses. |
| **Packages Router** | `routers/packages.py` | Package tracking catalog, detected breaking symbol records, and changelog diffs. |
| **Stats Router** | `routers/stats.py` | Centralized operator metrics: monitored repos, open PRs, pending patches, and breaking package counts. |
| **Webhooks Router** | `routers/webhooks.py` | Cryptographic HMAC-SHA256 verification (`X-Hub-Signature-256`) of incoming GitHub App webhook events. |
| **AST Code Scanner** | `services/code_scanner.py` | Tree-Sitter AST parser supporting TypeScript, TSX, JavaScript, and Python (`LANGUAGE_CONFIG`). |
| **Import Graph Engine** | `services/import_graph.py` | Multi-language static import extractor across TS, JS, Python, Go, Rust, Java, C/C++, Ruby, PHP. |
| **GitHub App Service** | `services/github_service.py` | Authenticated installation client: creates branches, synthesizes CI workflows, opens PRs, and publishes check runs. |
| **Crypto Subsystem** | `services/crypto.py` | Fernet symmetric key encryption for BYOK credentials. Keys are decrypted in-memory only. |
| **Job Queue Engine** | `jobs/queue.py` | PostgreSQL row-locking queue (`SELECT ... FOR UPDATE SKIP LOCKED`) with exponential backoff and fairness caps. |

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="endpoint-catalog"></a>03. Endpoint Catalog

### Authentication (`/api/auth`)
- `GET /api/auth/github`: Redirects to GitHub OAuth authorization.
- `GET /api/auth/callback`: Exchanges temporary authorization code for user session JWT.
- `GET /api/auth/me`: Validates session cookie and returns authenticated user identity.
- `GET /api/auth/logout`: Clears session authentication cookies.

### Repositories (`/api/repos`)
- `GET /api/repos`: Returns list of monitored repositories for the current user.
- `GET /api/repos/{id}`: Detailed view of a repository with detected changes and generated patches.
- `PATCH /api/repos/{id}`: Updates repository verification policies (`requires_tests`, `requires_typecheck`).

### 3D Repo Atlas (`/api/repos/{id}/atlas`)
- `GET /api/repos/{id}/atlas/graph`: Computes or returns cached 3D import graph (nodes, edges, folder depth, commit SHA).
- `GET /api/repos/{id}/atlas/file`: On-demand source code reader for 3D card inspection.
- `GET /api/repos/{id}/atlas/last-edited`: Retrieves last commit author and timestamp for a selected file.
- `GET /api/repos/{id}/incidents/stream`: Server-Sent Events (SSE) stream for real-time incident breakage notifications.

### Telemetry & Health (`/api/stats`, `/health`)
- `GET /api/stats`: Telemetry counter summary (monitored repos, packages, active patches, open PRs).
- `GET /health`: Health probe returning operational status and active LLM provider.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="job-queue"></a>04. PostgreSQL Queue Architecture

Telex eliminates external message broker dependencies (e.g., Redis or RabbitMQ) by leveraging PostgreSQL row-level locks:

```sql
SELECT * FROM jobs 
WHERE status = 'queued' AND run_at <= NOW()
ORDER BY priority ASC, created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

### Queue Reliability Guarantees
1. **Zero Double-Processing**: `SKIP LOCKED` ensures concurrent worker processes claim distinct jobs without race conditions.
2. **Crash Resilience**: Worker processes renew a heartbeat lease during job execution. If a worker dies, orphaned jobs automatically revert to `queued` status after lease expiration.
3. **Exponential Backoff**: Failed jobs retry with jittered exponential backoff up to configured threshold limits.
4. **Per-Installation Fairness**: Workers enforce concurrency caps per GitHub App installation, preventing a single high-volume organization from starving others.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="tree-sitter-ast"></a>05. Tree-Sitter AST Scanner

Regex searches generate severe false positives on comments, strings, and variable names that happen to match obsolete symbol identifiers.

Telex uses **Tree-Sitter C-bindings** to construct concrete syntax trees and evaluate structured query patterns:

```python
# Exact call site targeting across TypeScript, TSX, JS, and Python
LANGUAGE_CONFIG = {
    "typescript": {
        "call_node_type": "call_expression",
        "queries": [
            ("(call_expression function: (identifier) @fn)", "fn"),
            ("(call_expression function: (member_expression property: (property_identifier) @prop))", "prop"),
        ],
    },
    "python": {
        "call_node_type": "call",
        "queries": [
            ("(call function: (identifier) @fn)", "fn"),
            ("(call function: (attribute attribute: (identifier) @prop))", "prop"),
        ],
    },
}
```

Every matched call site records exact line numbers, byte offsets, and surrounding scope context for LLM patch synthesis.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="local-setup"></a>06. Local Setup & Execution

### 1. Virtual Environment & Dependencies
```bash
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Configuration
```bash
cp .env.example .env
```

Ensure the following variables are configured in `.env`:
- `DATABASE_URL`: PostgreSQL connection string (e.g. `postgresql+asyncpg://user:pass@localhost:5432/telex`).
- `TELEX_ENCRYPTION_KEY`: Fernet symmetric key generated via `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- `GEMINI_API_KEY`: Google Gemini API key (or BYOK keys configured via UI).
- `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`: GitHub App credentials.

### 3. Database Migrations
```bash
alembic upgrade head
```

### 4. Run API & Background Worker
```bash
uvicorn main:app --reload --port 8000
```

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="testing"></a>07. Verification & Test Suite

Run the full automated test suite:
```bash
pytest -v
```

Expected result:
```text
tests/test_code_scanner.py ............. PASSED
tests/test_patch_generation.py ......... PASSED
tests/test_github_service.py ........... PASSED
tests/test_queue.py .................... PASSED
tests/test_routers_stats.py ............ PASSED

======================= all test suites passed =======================
```

Run specific test modules:
```bash
# Tree-Sitter AST Scanner
pytest tests/test_code_scanner.py -v

# Patch Generation & Validation Sandboxes
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
