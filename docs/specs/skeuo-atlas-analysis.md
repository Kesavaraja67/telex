# Telex: Skeuomorphic UI + Incremental Repo Atlas + Evidence-Based Run Analysis
## Executable Spec — Phase 0 Output

> **Status:** Draft — awaiting plan-eng-review (Phase 3/4) and plan-design-review (Phase 2)
> **Branch discipline:** One PR per phase, no bundling.
> **Safety:** /careful active for entire run. /freeze scoped per phase as specified.

---

## Ground Truth (verified against current code — 2026-09-28)

| Fact | Location | Verified |
|------|----------|---------|
| Atlas full-scan: downloads entire tarball (capped 150 MB), re-parses every file serially, stores whole graph as one JSONB blob in RepoAtlasGraph.graph_json, unique on (repo_id, commit_sha). No reuse between commits. MAX_NODES = 6000. | apps/api/jobs/handlers/build_atlas_graph.py, services/repo_ingest.py, services/import_graph.py | yes |
| Webhook push handler uses _handle_push to enqueue update_atlas_graph (with fallback to build_atlas_graph on large diffs). | apps/api/routers/webhooks.py | yes |
| CameraRig.ts wheel handler: radius clamped 6 to 120, fixed look-at (0,-3,0). Left, middle, right mouse all orbit. No pan. No zoom-to-cursor. | apps/web/components/atlas/render/CameraRig.ts:104-111 | yes |
| AtlasScene.ts fog: THREE.FogExp2(0x000000, 0.018) — at r=120 visibility ~0%. Camera PerspectiveCamera(45, aspect, 0.1, 1000). | DESIGN.md:87, master prompt | yes |
| POST /repos/{id}/ai-explain exists. Prompt gets repo name, <=8 commits, dependency names. risk_score is LLM-invented. On failure: hardcoded risk_score=12, architecture_verdict=Nominal, degraded=true. | apps/api/routers/repos.py:118, services/patch_providers/gemini.py:282-299 | yes |
| globals.css existing tokens: --void, --surface-base, --surface-raised, --text-pure, --text-secondary, --text-muted, --border, --border-subtle, --accent-glow. Fonts: Space Grotesk, Geist Mono. | apps/web/app/globals.css:4-16 | yes |
| DESIGN.md mandates zero nested card boxes and flat cyber-minimal. Contradicts hybrid direction. Must be revised in Phase 1. | DESIGN.md:14 | yes |
| GET /api/repos/{repo_id}/atlas/graph reads from RepoAtlasGraph (single JSONB blob). Returns: status, repo_full_name, commit_sha, node_count, edge_count, truncated, graph. | apps/api/routers/atlas.py:46-154 | yes |
| AIExplainOut schema: summary, commit_insights, architecture_verdict, risk_score int, recommended_actions. | apps/api/schemas.py:76-81 | yes |
| TelexBot3D.tsx exists in apps/web/components/marketing/ — must not be changed (only its container may change). | apps/web/components/marketing/ | yes |

---

## PHASE 0: Spec and Plan Review (No Code)

**Deliverables:**
1. This document (docs/specs/skeuo-atlas-analysis.md) — per-phase executable spec.
2. docs/specs/phase3-4-eng-review.md — plan-eng-review output for Phases 3 and 4.
3. docs/specs/phase2-design-review.md — plan-design-review output for Phase 2.

**Gate:** Phase 1 must not start until all three documents exist.

---

## PHASE 1: Design System (hybrid skeuomorphic)

### Skills
/design-consultation -> /design-shotgun -> /design-html

### Scope
- Token definitions in apps/web/app/globals.css (extend, not fork).
- docs/design/controls.html reference page.
- DESIGN.md update (replace flat-cyber rules; keep 3D Atlas material doctrine unchanged).
- No React component built yet.

### Light model
Single virtual light source: top-left, ~35 degrees elevation.
CSS custom properties:
  --skeuo-light-angle: 145deg
  --skeuo-highlight-top: rgba(255,255,255,0.18)
  --skeuo-highlight-subtle: rgba(255,255,255,0.07)
  --skeuo-shadow-deep: rgba(0,0,0,0.65)
  --skeuo-shadow-mid: rgba(0,0,0,0.35)
  --skeuo-shadow-inner: rgba(0,0,0,0.5)

### Materials (token values)

Brushed dark metal (--metal-*): base=#1a1c1f, mid=#222427, light=#2e3136, shine=rgba(255,255,255,0.12)
Matte anodized panel (--panel-*): base=#141618, inset=#0e1012, rim=rgba(255,255,255,0.08)
Recessed black glass (--glass-*): base=#080a0c, rim-lit=rgba(255,255,255,0.15), rim-dark=rgba(0,0,0,0.8)
Rubberized key cap (--key-*): base=#1e2024, top=#252830, pressed=#191b1e, label=#d4d4d8

### Controls
- Tactile button: rest/hover/pressed/disabled; travel 1-2px translateY + inner shadow; spring settle 120ms
- Toggle switch: off/on/disabled; metal track, key thumb, LED at end
- LED lamp: off=#1a1c1f, ok=#14b8a6, warn=#f59e0b, fault=#f43f5e, busy=white pulse
- Engraved label: text-shadow 0 1px 0 rgba(255,255,255,0.08), 0 -1px 0 rgba(0,0,0,0.6)
- LED colors must not appear in 2D chrome outside LED elements

### Motion
- Button press: 80ms down, 120ms return, cubic-bezier(0.2,0,0,1)
- Button spring settle: 120ms, cubic-bezier(0.34,1.56,0.64,1)
- LED fade: 200ms ease-out
- prefers-reduced-motion: all transitions 0ms

### Typography
- Engraved label: color #6b7280, letter-spacing 0.08em, uppercase, 10px, font-mono
- text-shadow: 0 1px 0 rgba(255,255,255,0.09), 0 -1px 0 rgba(0,0,0,0.7)
- No new fonts. Keep Space Grotesk and Geist Mono.

### Token naming
New prefixes: --metal-*, --panel-*, --glass-*, --key-*, --skeuo-*, --led-*
Must coexist with existing --void, --surface-*, --border*, --font-*

### Acceptance criteria
- All tokens in globals.css
- docs/design/controls.html exists
- DESIGN.md updated (hybrid; Atlas 3D doctrine unchanged)
- No React component changed
- /design-review contrast pass (WCAG AA: all text >= 4.5:1)
- /design-shotgun: 3 variants; user picks one
- /design-html: chosen variant -> controls.html

---

## PHASE 2: Frontend Migration (UI Only)

### Freeze scope: apps/web ONLY. Zero changes to apps/api/.

### Scope order
1. Shared UI components (apps/web/components/ui/): Button, Badge, SpotlightCard, BorderBeam, TickerRibbon, CyberSkeleton. Keep prop APIs stable.
2. Dashboard shell (layout.tsx, sidebar, top bar): chassis with bezel, engraved nav, LED for daemon status.
3. Pages: dashboard, repos, repos/[id] (layout/controls only), activity, settings (toggles -> physical switches; buttons -> key caps).
4. Landing (components/marketing/*): re-frame in hardware language. TelexBot3D.tsx container -> recessed bezel only. Scene/model/camera/animation UNTOUCHED.
5. Atlas shell (frontend chrome only; camera Phase 3): HUD, legend, repo selector, CodePreviewPanel.tsx -> instrument surfaces. Legend -> lamp-and-label rows.
6. Loading states: keep skeleton pattern; restyle to new materials.

### Verification
- /design-review: consistent light direction, no AI-slop
- /qa: full pass on landing, dashboard, repos, repo detail, atlas, settings
- /browse: screenshots at 1440, 1024, 390px for every page, before and after, saved to docs/design/screens/
- git diff: zero files under apps/api/ changed
- TelexBot3D.tsx: file hash unchanged

### Gaps flagged
- Gap P2-1: Exact component file list in components/ui/ must be enumerated before work starts. Names like RadialButton, IllocaButton, KineticHeader may not exist at those exact paths.
- Gap P2-2: BorderBeam (@keyframes at globals.css L78) — confirm not used by TelexBot3D.tsx before removing/replacing.

---

## PHASE 3: Incremental Repo Atlas + Camera

### Freeze scope: apps/api/ + apps/web/components/atlas/ + apps/web/app/dashboard/

### 3A. Data Model (Alembic migration, additive)

New tables (RepoAtlasGraph untouched):

atlas_nodes: PK (repo_id, path). Columns: name, dir, depth, ext, language, is_binary, size_bytes, content_hash, unresolved_specifiers JSONB, updated_sha.
Index: ix_atlas_nodes_repo on (repo_id).

atlas_edges: PK (repo_id, source_path, target_path). Columns: kind, updated_sha.
Index: ix_atlas_edges_target on (repo_id, target_path). This is the reverse-import index.
FK: (repo_id, source_path) -> atlas_nodes(repo_id, path) ON DELETE CASCADE.

atlas_state: PK repo_id. Columns: head_sha, status (idle|updating|full_scan|failed), error_message, last_full_scan_sha, last_full_scan_at, alias_config_hash, updated_at.

Migration rules:
- Forward: create tables. Do NOT drop repo_atlas_graphs.
- Rollback: drop new tables only. repo_atlas_graphs untouched.

### 3B. Change Detection

Push path (routers/webhooks.py line 58 stub):
- Gate: only pushes to repo's default branch.
- Extract added/modified/removed from commits[*].added/modified/removed.
- Rename detection via GitHub compare API GET /repos/{repo}/compare/{base}...{head} when push > 20 commits or remove+add pair detected.
- Enqueue update_atlas_graph job with {repo_id, base_sha, head_sha, changed: {added, modified, removed, renamed}}.
- Deduplicate: skip if job for (repo_id, head_sha) already queued or running.

Manual refresh (GET /atlas/graph?refresh=true):
- Compute diff from atlas_state.head_sha to current head via compare API.
- Enqueue same job.

Race condition guard (inside job handler):
- Write atlas_state.head_sha = head_sha only WHERE head_sha = base_sha OR head_sha IS NULL.
- If newer head_sha already exists, abort silently.

### 3C. Incremental Update Algorithm (services/atlas_incremental.py, new)

1. Fetch only changed file contents (GitHub Contents API, concurrency cap: 8). Skip files > 2 MB.
2. Skip re-parse when content_hash matches stored value.
3. Re-parse changed files using refactored single-file parser from import_graph.py.
   Existing build_import_graph() behavior and tests must remain green.
4. Update steps:
   a. MODIFIED: delete old outgoing edges; insert new edges.
   b. REMOVED: delete node; cascade-delete outgoing edges; mark importers' unresolved_specifiers.
   c. ADDED: insert node + outgoing edges; re-resolve unresolved specifiers from other nodes that match new path.
   d. RENAMED old_path -> new_path: UPDATE atlas_edges source_path + target_path; uses reverse index.
5. Alias config change (tsconfig.json, jsconfig.json): if alias_config_hash changes, re-resolve ALL JS/TS edges.
6. Full transaction: on failure, rollback; set status='failed'.
7. On success: update atlas_state(head_sha, status='idle').

Full-scan fallbacks (use existing tarball path, write to normalized tables):
- First load (no atlas_state row).
- Diff > 40% of current node count.
- last_full_scan_at older than 7 days.

### 3D. API Changes (routers/atlas.py)

GET /atlas/graph — same shape + new fields: delta {added, removed, changed}, head_sha, last_full_scan_at, mode (incremental|full).

New endpoint: GET /atlas/node/{path}/neighbors
Returns: {path, imports: [paths], imported_by: [paths]}. Uses ix_atlas_edges_target.

Keep unchanged: /file, /last-edited.

### 3E. Frontend Behavior

Delta rendering (AtlasScene.ts — patch scene, no full rebuild):
- Added cards: fade-in 200ms.
- Removed cards: fade-out 200ms then splice.
- Changed cards: single 100ms pulse.
- prefers-reduced-motion: skip all animations.

Status lamp: idle / updating N files / full scan / failed — from atlas_state.status.

Inspector drawer: importers + importees from /neighbors; click-to-focus camera.

### 3F. Camera and Fog Fixes (CameraRig.ts, AtlasScene.ts)

Current bugs confirmed:
- Wheel: radius [6, 120] fixed look-at (0,-3,0). No cursor zoom.
- Mouse: all 3 buttons orbit. No pan.
- Fog: FogExp2(0x000000, 0.018) — at r=120 ~88% invisible.

Fixes:
1. Zoom to cursor: raycast pointer to graph plane; move lookAt toward world point proportional to zoom step.
2. Pan: right-drag + Space+drag + middle-drag pan lookAt in camera screen plane. Left-drag = orbit.
3. Range: minRadius=1.5, maxRadius=6*graphBoundingRadius (from layout bounding box). Camera far = graphBoundingRadius*8+100.
4. Fog fix: density = 0.51 / maxRadius (derived from target: 60% visibility at maxRadius). Cards/wires: opacity floor 0.1.
5. Controls: F=fit, +/-=zoom, arrow keys=pan, Esc=deselect. Touch: pinch=zoom, two-finger drag=pan.
6. Keep spring smoothing. Keep prefers-reduced-motion.

### 3G. Verification

- /investigate: reproduce slow full-scan and zoom/fog bugs. Record baseline timings.
- /benchmark: (a) first full scan, (b) incremental 1/10/100 files, (c) FPS at 2000 nodes.
  Pass criterion: incremental 1-10 files must be >= 10x faster than full scan.
- Tests (apps/api/tests/test_atlas_incremental.py): rename, delete, add-resolves-unresolved, alias-change, two-racing-pushes, truncated-push-payload, first-load-fallback, 7-day-fallback, full-vs-incremental-equivalence.
- /cso: HMAC verification confirmed; path traversal in file paths; GitHub token scope; resource exhaustion.
- Coverage gate: 80% maintained.

### Gaps flagged (Phase 3)
- Gap P3-1: Rename detection — compare API adds one extra call per push with remove+add pair. Needs rate-limit budget.
- Gap P3-2: Alias re-resolution scope — propose 8 concurrent, 30s timeout before full-scan fallback.
- Gap P3-3: Write amplification — batch DELETE WHERE source_path = ANY(...) + bulk INSERT ON CONFLICT.
- Gap P3-4: 40% threshold — node count must be fetched first (SELECT COUNT) before fetching file content.

---

## PHASE 4: Run Analysis

### Skills
/plan-ceo-review -> /spec -> /plan-eng-review -> /design-shotgun -> /design-html -> /review -> /qa -> /ship

### Principle
Score is computed from facts. LLM only writes prose about those facts. LLM never invents a number.

### 4A. Signals (services/repo_analysis.py, new)

Structure signals (from atlas_nodes + atlas_edges):
- Circular import chains: Tarjan SCC. Output: list of cycle paths.
- Hub files fan-in/fan-out: top 10 by import count.
- Orphan files: 0 incoming + 0 outgoing edges.
- Unresolved internal imports: count per file from unresolved_specifiers.
- Deepest dependency chain: longest path in DAG.
- Folder coupling: cross-folder edge density.

Dependency health (from scanner/detected-change tables):
- Packages behind latest version.
- Packages with breaking change + N call sites.
- Deprecated API usage.

Telex track record (from existing tables):
- Patches generated, verified, merged, rejected.
- Open PRs waiting on human review.

Delivery safety (from GitHub API + atlas data):
- Test files present (path LIKE %test% OR %spec%).
- CI workflow present (.github/workflows/*.yml in atlas_nodes).
- Last CI status (GitHub Checks API for head_sha).

Activity (from GitHub commits API):
- Churn on hub files over last 30 days.

### 4B. Score

score = structure*0.30 + dependency*0.30 + change_safety*0.25 + verification*0.15

Sub-score factors:
- structure_score: -10 per cycle, -5 per hub file (fan-in > 30), -3 per 10% orphan ratio, +10 if no unresolved imports
- dependency_score: -20 per package with breaking change, -5 per package behind major version
- change_safety: -15 if no tests, -10 if no CI, -5 per high-churn hub file
- verification: +20 if merge_rate > 0.8, +15 if pass_rate > 0.9, -10 if > 3 open human-review PRs

Degraded state: if signal unavailable, sub-score = null. Compute total over available ones. Display not measured.
NEVER return a fabricated score. Delete hardcoded risk_score:12 from gemini.py:293.

Weights in services/analysis_weights.py (single source of truth).

### 4C. Findings

Each finding: severity (critical|warning|info), title (<=80 chars), evidence (real paths/counts), why_it_matters, what_to_do, atlas_deep_link (?focus=paths).
Disqualified: any finding with no evidence or no what_to_do.

### 4D. LLM Use

Input: structured JSON of computed signals + findings.
Output: executive_summary (<=200 words) + do_this_first (from provided findings only).
Validate: reject any recommendation referencing file/package not in input.
Fallback: if LLM fails, show all computed sections; only executive_summary shows unavailable.

### 4E. Endpoints and UI

POST /repos/{id}/ai-explain — backward-compatible (new fields added; old fields kept).
GET /repos/{id}/analysis — returns {latest, previous, delta_score}.

New table repo_analysis_runs: id, repo_id, head_sha, score, sub_scores JSONB, findings JSONB, signals JSONB, created_at.
Index: ix_repo_analysis_runs_repo on (repo_id, created_at DESC).

UI (Phase 1 material language, repo detail page):
- Score dial (real needle at computed position).
- Four sub-score gauges with weight labels and not-measured state.
- Delta badge vs previous run.
- Do this first action list (from LLM, sourced from findings only).
- Findings list: severity LED + title + evidence + Atlas deep-link.
- Trend strip from stored runs.
- Empty/first-run state: explicit CTA (not blank).
- Partial-data state: show available, label missing.

### Gaps flagged (Phase 4)
- Gap P4-1: poll_registry may not store PyPI/npm latest version — verify before implementing dependency_score.
- Gap P4-2: GitHub Checks API requires checks:read scope — verify GitHub App manifest.
- Gap P4-3: Score weights are proposed baseline — founder review required before Phase 4 ships.
- Gap P4-4: risk_score field name kept for backward compat but populated from deterministic score, not LLM.

---

## PHASE 5: Close-out

### Skills: /document-release -> /health -> /retro

README.md, ARCHITECTURE.md, DESIGN.md, CONTRIBUTING.md updated.
/health: coverage maintained at 80%, no regressions.
/retro: benchmark numbers before/after, what shipped, what was cut.

---

## Open Gaps Summary

| ID | Phase | Gap | Decision needed by |
|----|-------|-----|-------------------|
| P2-1 | 2 | Exact component file list in components/ui/ | Before Phase 2 starts |
| P2-2 | 2 | BorderBeam used in TelexBot3D.tsx? | Before Phase 2 starts |
| P3-1 | 3 | Push rename detection extra compare API call | Phase 3 eng review |
| P3-2 | 3 | Alias re-resolution concurrency cap + timeout | Phase 3 eng review |
| P3-3 | 3 | Write amplification batching strategy | Phase 3 eng review |
| P3-4 | 3 | 40% threshold computation order | Phase 3 eng review |
| P4-1 | 4 | poll_registry latest-version storage | Before Phase 4 starts |
| P4-2 | 4 | GitHub App checks:read scope | Before Phase 4 starts |
| P4-3 | 4 | Score weights: product decision | Before Phase 4 ships |
| P4-4 | 4 | risk_score backward-compat field | Before Phase 4 starts |

---

## Decisions Already Made (not reopened)

1. Design direction: Hybrid — dark 3D scenes + metal control surfaces.
2. Run Analysis audience: developers and engineering leads, action-first.
3. Atlas update triggers: both (automatic on push + manual refresh).
4. TelexBot3D.tsx: untouched. Container may become recessed bezel.
5. Phase 2 is strictly UI — no API/DB changes.
