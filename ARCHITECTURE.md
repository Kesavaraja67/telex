<a id="top"></a>

<div align="center">

  <h1>Telex System Architecture & Technical Specification</h1>
  <p><b>Autonomous AI Self-Healing Patch Substrate & 3D Architectural Cartography</b></p>

  <p>
    <a href="https://github.com/astral-sh/ruff">
      <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square" alt="Ruff" />
    </a>
    <img src="https://img.shields.io/badge/Architecture-Distributed%20Workers-14B8A6?style=flat-square" alt="Architecture" />
    <img src="https://img.shields.io/badge/Queue-Postgres%20SKIP%20LOCKED-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL SKIP LOCKED" />
    <img src="https://img.shields.io/badge/Parser-Tree--Sitter%20AST-050508?style=flat-square" alt="Tree-Sitter AST" />
    <img src="https://img.shields.io/badge/Governance-Zero%20Automerge-F43F5E?style=flat-square" alt="Zero Automerge" />
  </p>

  <br>

  <p>
    <a href="#topology"><b>System Topology</b></a> &nbsp;•&nbsp;
    <a href="#tree-sitter"><b>Tree-Sitter AST</b></a> &nbsp;•&nbsp;
    <a href="#ci-sandboxes"><b>CI Verification</b></a> &nbsp;•&nbsp;
    <a href="#security-crypto"><b>Security & Crypto</b></a> &nbsp;•&nbsp;
    <a href="#repo-atlas"><b>3D Repo Atlas</b></a> &nbsp;•&nbsp;
    <a href="#queue-engine"><b>Fair Queue</b></a>
  </p>

</div>

<br>

---

<br>

## <a id="topology"></a>01. Executive System Topology

Telex functions as an asynchronous, event-driven daemon designed to close the gap between upstream library releases and downstream repository health. It continuously monitors registry indices, parses breaking changes, projects codebase structure in 3D, synthesizes precision unified diffs via LLMs, and verifies each patch in an isolated CI runner before opening a human-reviewed Pull Request.

```text
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   INGESTION LAYER                                      │
 └────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                          [ Upstream Registry Notifications ]
                            - npm & PyPI registry polling (watches packages 24/7)
                            - Package version updates & changelog discovery
                            - Breaking interface diffs
                                             │
                                             ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                               AST CODE SCANNER LAYER                                   │
 │       (Tree-Sitter Multi-Language Scanner: TypeScript, TSX, JavaScript, Python)        │
 └────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     ▼                                               ▼
 ┌───────────────────────────────────────┐       ┌───────────────────────────────────────┐
 │     3D REPO ATLAS & BLAST RADIUS      │       │      LLM REPAIR SYNTHESIS LAYER       │
 │          (/dashboard/atlas)           │       │ (Gemini 2.5 Flash / Claude / OpenAI)  │
 ├───────────────────────────────────────┤       ├───────────────────────────────────────┤
 │ - Multi-language AST import graph     │       │ [ Pinpoint Exact Usages & Offsets ]   │
 │ - Layered 3D force layout (Y/X/Z)     │       │ - Unified patch diff synthesis        │
 │ - Live SSE breakage pulse overlay     │       │ - Multi-candidate best-of-3 selection │
 │ - Real-time visual failure cascade    │       │ - git apply structural filter         │
 └───────────────────────────────────────┘       └───────────────────────────────────────┘
                                                                     │
                                                                     ▼
                                                 ┌───────────────────────────────────────┐
                                                 │      EPHEMERAL VERIFICATION GATE      │
                                                 │ (Isolated Clone Sandbox & Native CI)  │
                                                 │  Typechecks (tsc / mypy) + Test Suites│
                                                 └───────────────────────────────────────┘
                                                                     │
                                                             [ 100% Verified ]
                                                                     │
                                                                     ▼
                                                 ┌───────────────────────────────────────┐
                                                 │      PULL REQUEST DELIVERY LAYER      │
                                                 │       (Human-Reviewed GitHub PR)      │
                                                 └───────────────────────────────────────┘
```

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="tree-sitter"></a>02. Multi-Language Tree-Sitter AST Scanner

Regex-based search produces unacceptable false positives by matching comments, docstrings, and unrelated variables.

Telex uses **Tree-Sitter AST queries** configured through a centralized `LANGUAGE_CONFIG` architecture:

```python
LANGUAGE_CONFIG = {
    "typescript": {
        "parser_name": "typescript",
        "extensions": {".ts", ".mts", ".cts"},
        "call_node_type": "call_expression",
        "queries": [
            ("(call_expression function: (identifier) @fn)", "fn"),
            ("(call_expression function: (member_expression property: (property_identifier) @prop))", "prop"),
        ],
    },
    "tsx": {
        "parser_name": "tsx",
        "extensions": {".tsx"},
        "call_node_type": "call_expression",
        "queries": [
            ("(call_expression function: (identifier) @fn)", "fn"),
            ("(call_expression function: (member_expression property: (property_identifier) @prop))", "prop"),
        ],
    },
    "javascript": {
        "parser_name": "javascript",
        "extensions": {".js", ".jsx", ".mjs", ".cjs"},
        "call_node_type": "call_expression",
        "queries": [
            ("(call_expression function: (identifier) @fn)", "fn"),
            ("(call_expression function: (member_expression property: (property_identifier) @prop))", "prop"),
        ],
    },
    "python": {
        "parser_name": "python",
        "extensions": {".py"},
        "call_node_type": "call",
        "queries": [
            ("(call function: (identifier) @fn)", "fn"),
            ("(call function: (attribute attribute: (identifier) @prop))", "prop"),
        ],
    },
}
```

Every discovered usage returns exact character and byte offsets, line numbers, and the isolated syntax node snippet for minimal LLM context windows.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="ci-sandboxes"></a>03. Ephemeral Sandbox Verification Gate

Telex never assumes that an LLM-generated patch is bug-free. Instead of relying on simulated diff parsers or local system clones that diverge from the target repository, Telex uses a **native verification gate**:

1. **Candidate Branch Creation**: Telex creates a dedicated verification branch: `telex/validate-<patch-id>`.
2. **Atomic Verification Bundle**: Commits the candidate unified patch applied to the target code.
3. **Native Runner Execution**: Executes the target repository's **real package dependencies, typecheckers, and test runner** on clean runners.
4. **Autonomous Status Polling**: Monitors check runs with bounded exponential backoff.
5. **Strict Gate Rules**:
   - **PASS (100% Green)** → Clean pull request opened with detailed verification receipts.
   - **FAIL** → Bounded retry with compiler feedback, or immediate rejection. **Zero hallucinated code ever reaches a production pull request.**

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="security-crypto"></a>04. Security Architecture & Cryptographic Boundaries

- **Fernet Secret Encryption**: BYOK API keys are encrypted at rest using AES-128-CBC with HMAC-SHA256 authenticated Fernet tokens. Decryption occurs only in volatile memory when instantiating the LLM provider client.
- **Strict Log Scrubbing**: Global logging filter inspects every stdout line and scrubs `sk-*`, `AIza*`, `sk-ant-*`, and high-entropy authentication tokens before writing to disk.
- **Cryptographic Webhook Validation**: All inbound GitHub webhooks are cryptographically authenticated via HMAC-SHA256 (`X-Hub-Signature-256`) against `GITHUB_WEBHOOK_SECRET`.
- **Absolute Non-Negotiable: Never Auto-Merge**: Telex opens pull requests. A human engineer merges them. Under no condition, at any confidence threshold, does Telex merge code automatically.
- **Cross-Origin Authenticated Sessions**: Authentication between the Next.js frontend (Vercel) and FastAPI backend (Render) uses HttpOnly session tokens with `/api/auth/me` verification and strict origin whitelisting.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="repo-atlas"></a>05. Repo Atlas: 3D Layered Spatial Engine

Accessible via the dedicated operator page `/dashboard/atlas`, Repo Atlas transforms abstract directory trees into an interactive 3D spatial graph:

```text
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                              REPO SNAPSHOT & INGESTION                                 │
 │           GitHub tarball download · Zero per-file API rate-limit exhaustion            │
 └────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                         MULTI-LANGUAGE AST GRAPH PARSER                                │
 │       Tree-Sitter: TS, JS, Python, Go, Rust, Java, C/C++, Ruby, PHP + tsconfig paths   │
 └────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                       LAYERED 3D FORCE-DIRECTED LAYOUT                                 │
 │         Folder hierarchy on Y-axis · d3-force-3d polar collision layout on X/Z         │
 └────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                         DYNAMIC THREE.JS CANVAS HUD                                    │
 │        512x320 Canvas Card Textures · Glowing Wire Conduits · SSE Breakage Overlay    │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

### Depth Axis Stratification ($Y$)
Directory hierarchy is strictly mapped to the negative vertical axis:
$$Y = -\text{depth} \times 4.8$$
- Root files and top-level modules reside at $Y = 0$.
- Submodules and internal libraries descend downward without overlapping vertical planes.

### Polar Coordinate Layout ($X, Z$)
Sibling folders at the same depth level are distributed along concentric polar rings:
$$\text{radius} = 4.8 + 0.85 \times \text{siblingCount}$$
Individual file cards cluster around their folder anchor with constrained 2D collision repulsion.

### Role in the Autonomous Pipeline
1. **Blast Radius Visualization**: When an upstream dependency change is discovered, Repo Atlas calculates the transitive closure of affected callers and illuminates them across 3D space.
2. **Real-Time Breakage Overlay (SSE)**: Subscribes to `/api/repos/{id}/incidents/stream` to flash severed cables and affected cards in rose-crimson (`#E11D48`).
3. **In-Canvas Source Review**: Operators click any card to inspect syntax-highlighted source code, call sites, and Git commit metadata prior to merging.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="queue-engine"></a>06. PostgreSQL SKIP LOCKED Fair Queue

Telex avoids external message broker dependencies by implementing atomic, concurrent job processing directly in PostgreSQL:

```sql
SELECT * FROM jobs 
WHERE status = 'queued' AND run_at <= NOW()
ORDER BY priority ASC, created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

- **Fair-Share Multi-Tenancy**: Enforces concurrency caps per GitHub installation, preventing noisy-neighbor starvation.
- **Heartbeat Leases**: Active jobs refresh heartbeat timestamps. If a worker terminates abruptly, orphaned jobs are reclaimed automatically.
- **Exponential Backoff**: Transient network or rate-limit errors retry with exponential backoff and jitter.

<br>

<div align="center">
  <a href="#top">
    <img src="https://img.shields.io/badge/%E2%86%91-Back%20to%20Top-050508?style=flat-square&logoColor=white" alt="Back to Top" />
  </a>
</div>
