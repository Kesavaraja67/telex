# Telex System Architecture & Technical Specification

> **Autonomous AI Self-Healing Patch Agent for Codebase Dependencies**

---

## 1. Executive System Topology

Telex operates as an asynchronous, event-driven daemon that continuously tracks upstream library releases, detects breaking symbol changes, maps codebase import topologies and failure blast radii in an interactive 3D Repo Atlas, synthesizes precision unified diffs using LLMs, and verifies every patch inside a native CI sandbox before opening a human-reviewed Pull Request.

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

---

## 2. Multi-Language AST Code Scanner Architecture

A critical engineering advantage of Telex is that it avoids regex or textual search when detecting breaking change impacts. Regex searches produce false positives on comments, strings, and unrelated identifiers.

Telex uses **Tree-Sitter AST queries** configured through a unified `LANGUAGE_CONFIG` architecture:

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

---

## 3. Ephemeral GitHub Actions Verification Gate

Telex never assumes that an LLM-generated patch is bug-free. Instead of relying on simulated diff parsers or local system clones that diverge from the target repository, Telex uses a **native verification gate**:

1. **Candidate Branch Creation**: Telex creates a dedicated verification branch:  
   `telex/validate-<patch-id>`
2. **Atomic Verification Bundle**: Using PyGithub's Git Data API, Telex commits:
   - The candidate unified patch applied to the target code.
   - An auto-generated verification workflow: `.github/workflows/telex-verify.yml`.
3. **Native Runner Execution**: The environment executes the target repository's **real package dependencies, typecheckers, and test runner** on clean runners.
4. **Autonomous Status Polling**: Telex monitors the check runs via the GitHub API with bounded exponential backoff.
5. **Gating Rule**:
   - **PASS (100% Green)** → Clean pull request opened with detailed verification receipts.
   - **FAIL** → Bounded retry with compiler feedback, or immediate rejection. **Zero hallucinated code ever reaches a production pull request.**

---

## 4. Security Model & Deliberate Stop Safety Guardrails

- **Cryptographic Webhook Validation**: All inbound GitHub webhooks are cryptographically authenticated via HMAC-SHA256 (`X-Hub-Signature-256`) against `GITHUB_WEBHOOK_SECRET`.
- **Absolute Non-Negotiable: Never Auto-Merge**: Telex opens pull requests. A human engineer merges them. Under no condition, at any confidence threshold, does Telex merge code automatically.
- **Cross-Origin Authenticated Sessions**: Authentication between the Next.js frontend (Vercel) and FastAPI backend (Render) uses HttpOnly session tokens with `/api/auth/me` verification and strict origin whitelisting.
- **Production Secret Guard**: In `ENVIRONMENT=production`, the API process fails loudly at boot if required credentials (`GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `NEXTAUTH_SECRET`) are missing or using development defaults.

---

## 5. Repo Atlas: 3D Layered Architecture & AST Dependency Visualizer

Telex features a real-time, interactive 3D architecture visualizer accessible via the dedicated operator page `/dashboard/atlas`.

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

### 5.1 Architecture Pipeline
1. **Durable Ingestion & Snapshotting**:
   - Downloads GitHub's codeload tarball for the target branch in one authenticated request scoped to the installation token (`services/repo_ingest.py`).
   - Extracts directory trees safely with path traversal guards.
2. **Multi-Language AST Import Graph Extraction**:
   - `services/import_graph.py` traverses the codebase and invokes Tree-Sitter parsers for:
     - **TypeScript, TSX, JavaScript**: `import`, `require`, dynamic `import()`, and `tsconfig.json` path aliases (`@/*`).
     - **Python**: `from . import ...`, package-root absolute imports, and `__init__.py` modules.
     - **Go, Rust, Java, C, C++, Ruby, PHP**: native import syntax queries.
   - De-duplicates edges and logs unresolved imports transparently.
3. **Layered 3D Spatial Layout Engine**:
   - Folder hierarchy is projected deterministically along polar coordinates on the Y-axis (`LayeredLayout.ts`).
   - File cards settle into non-overlapping concentric positions using constrained 3D force simulation (`d3-force-3d`).
4. **Dynamic High-Fidelity Rendering**:
   - Card textures are dynamically rasterized onto crisp 512x320 canvas textures (`CardTextureAtlas.ts`) with custom language badges and live last-edited commit metadata.
   - Animated glowing wire conduits render static import dependencies (`WireRenderer2.ts`).
5. **Real-Time Breakage Overlay**:
   - Subscribes to Server-Sent Events (`/api/repos/{id}/incidents/stream`) to immediately pulse broken files and dependencies in vivid rose (`#E11D48`) when an upstream dependency change breaks code usages.
6. **Dedicated Operator Surface**:
   - Centralized on `/dashboard/atlas` with repository switching dropdown, camera reset (`F`), live refresh (`R`), legend toggle (`L`), and direct drilldown to patch generation.

### 5.2 Role in the Autonomous Self-Healing Pipeline
Repo Atlas directly completes the loop between upstream package surveillance and autonomous LLM repair:
- **Exposing the Blast Radius**: When `poll_registry` detects an upstream breaking release and `extract_changes` identifies obsolete symbols, `scan_repo` isolates the primary call sites. Repo Atlas maps the **transitive failure blast radius** across all internal import conduits in 3D so engineers see exactly which modules are impacted.
- **In-Flight Visual Incident Pulse**: While Telex queues `generate_patch` to call the LLM and `validate_patch` to run ephemeral CI test suites, Repo Atlas illuminates broken files and severed conduits in vivid red (`#E11D48`) via real-time SSE streams (`/api/repos/{id}/incidents/stream`).
- **Pre-Merge Structural Inspection**: Operators can click any 3D card on `/dashboard/atlas` to read syntax-highlighted code, check last-commit metadata, trace connected callers, and verify that the LLM's synthesized diff cleanly isolates the failure before merging the PR.
