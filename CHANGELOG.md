# Changelog

All notable changes to Telex are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Telex uses [Conventional Commits](https://www.conventionalcommits.org/) — every
`feat:`, `fix:`, `docs:`, and `chore:` entry below maps directly to a commit or
pull request that you can look up in the [commit history](https://github.com/Kesavaraja67/telex/commits/main).

---

## [Unreleased]

### Added
- Skeuomorphic galvanometer dial instrument card (`RunAnalysisCard.tsx`) for
  displaying deterministic architectural resilience scores.
- Phase 4 repo analysis engine: Tarjan SCC cycle detection, hub-file fan-in
  scoring, dependency blast-radius sub-scores, and LLM-written executive
  summaries constrained to computed facts (`services/repo_analysis.py`,
  `services/analysis_weights.py`).
- `RepoAnalysisRun` database model and `/repos/{id}/analysis` API endpoint.
- Incremental Atlas graph update handler (`jobs/handlers/update_atlas_graph.py`)
  triggered on GitHub `push` webhooks.
- `AbortSignal.any()` combined cancellation in `apiFetch` so both caller-provided
  signals and the built-in timeout fire correctly.
- Boundary-safe path resolution in the 3D Atlas `focusPath` node lookup.

### Fixed
- Failed GitHub App syncs no longer poison `_LAST_SYNC_TIME`, keeping repos
  eligible for the initial-sync retry path.
- Metadata cache is only written when at least one GitHub API request succeeds.
- Background sync tasks are now deduplicated via `_SYNC_TASK` module variable.
- Repository loading screen no longer flashes a false not-found state on timeouts.
- `API_BASE` now uses `getApiUrl()` so Atlas and incident SSE requests use the
  same localhost-aware backend selection as `apiFetch`.
- CodeQL high-severity URL substring sanitization in `getApiUrl()`.
- `controller.abort()` now passes a `DOMException("...", "TimeoutError")` for
  spec-compliant timeout identification.

---

## [0.9.0] — 2026-09 (Phase 3: Incremental Atlas)

### Added
- Incremental Repo Atlas graph engine: `AtlasNode`, `AtlasEdge`, `AtlasState`
  models with O(1) reverse-dependency lookups via `ix_atlas_edges_target` index.
- Webhook-triggered incremental graph updates on every `push` event.
- Live SSE incident event stream (`/incidents/{id}/events`).
- `CodePreviewPanel` slide-in AST card inspector with line-level import references.
- Catenary conduit wire physics in Three.js scene (`WireRenderer2.ts`).

### Fixed
- npm audit — `brace-expansion` vulnerability patched.

---

## [0.8.0] — 2026-08 (Phase 2: 3D Atlas + BYOK)

### Added
- Interactive 3D Repo Atlas at `/dashboard/atlas` powered by Three.js and
  d3-force-3d with depth stratification and deterministic polar layout.
- BYOK (Bring Your Own Key) API key management — Fernet AES-128 encryption at
  rest for 10 LLM providers.
- `UserApiKey` model and `/settings/keys` management UI.
- Blast-radius 3D failure propagation visualization.

---

## [0.7.0] — 2026-07 (Phase 1: Core Pipeline)

### Added
- Six-stage automated dependency healing pipeline:
  `poll_registry` -> `extract_changes` -> `scan_repo` -> `generate_patch` ->
  `validate_patch` -> `open_pr`.
- PostgreSQL `SKIP LOCKED` fair-queue worker with per-tenant fairness caps.
- Tree-Sitter AST call-site scanner for TypeScript, TSX, JavaScript, and Python.
- Multi-provider LLM patch synthesis (Gemini, Claude, OpenAI, Groq, Mistral,
  DeepSeek, xAI, Cohere, Together AI, Nvidia Nemotron).
- HMAC-SHA256 GitHub webhook verification.
- HttpOnly SameSite JWT session cookies.
- GitHub App OAuth flow and installation webhook handlers.

---

> **Contributing to this file**: When you open a pull request, add a one-line
> entry under `[Unreleased]` in the appropriate section (`Added`, `Fixed`,
> `Changed`, `Removed`). The maintainer moves entries to a versioned section on
> release.
