# Repo Atlas — 3D Full-Repo Structural Code Visualizer & Blast Radius Engine

Repo Atlas renders a persistent, whole-repository 3D structural map of any connected codebase in Telex. It works directly alongside Telex's package watchdog and LLM repair pipeline: while Telex watches npm & PyPI packages for breaking changes, Repo Atlas maps out the entire repository AST, illuminates failure blast radii in real time, and gives operators visual inspection of the code before the LLM patch is merged.

---

## 1. Architecture Overview

```
apps/web/app/dashboard/atlas/page.tsx (Dedicated operator page with repo switcher dropdown)
  └─ AtlasView.tsx (HUD, polling, SSE event handling, keyboard shortcuts)
       ├─ AtlasScene.ts (Three.js scene, lighting, camera orbit, camera reset & focus)
       │    ├─ LayeredLayout.ts (hierarchical folder depth Y + 2D X/Z force simulation)
       │    ├─ CardTextureAtlas.ts (512x320 canvas card textures & language badges)
       │    ├─ WireRenderer2.ts (hierarchy lines + bezier import wires + breakage pulses)
       │    ├─ DragController.ts (raycasting + horizontal plane drag constraint)
       │    └─ lastEditedCache.ts (lazy debounced commit metadata fetching)
       └─ CodePreviewPanel.tsx (slide-in syntax-highlighted code reader + breakage banner)
```

---

## 2. Layered Layout Algorithm (`LayeredLayout.ts`)

1. **Strict Folder-Depth Stratification (Y axis)**:
   - $Y = -\text{depth} \times \text{LAYER\_SPACING}$ (where `LAYER_SPACING = 3.2`).
   - Root files and top-level directories rest at $Y = 0$.
   - Depth 1 rests at $Y = -3.2$, depth 2 at $Y = -6.4$, etc.
   - Y is locked and excluded from physics simulation so folder structure is never distorted.

2. **Deterministic Polar Folder Anchors (X and Z axes)**:
   - Sibling folders at the same depth are distributed in polar rings around their parent anchor:
     $$\text{radius} = 2.8 + 0.45 \times \text{siblingCount}$$
   - This layout is deterministic and stable across reloads for the same commit SHA.

3. **Local Card Clusters & 2D Collision Avoidance**:
   - Files within a folder are seeded in concentric rings around their folder anchor.
   - A constrained 2D force pass (`d3-force-3d`) runs `forceX` and `forceZ` toward the anchor, with `forceCollide` clearance to eliminate card overlap without shifting Y.

---

## 3. Card Visual Specification (`CardTextureAtlas.ts`)

Each file card is a 16:10 world plane (`1.6 × 1.0` units) backed by a 512×320 canvas texture:
- **Card Body**: Void glass fill `rgba(255, 255, 255, 0.03)` over pure black with a 1px border.
- **Row 1**:
  - Top-Left: Rounded language badge chip (e.g. `TS`, `TSX`, `JS`, `PY`, `{}`, `MD`).
  - Top-Right: Last-edited relative timestamp (e.g. `3d ago`, `2h ago`) or skeleton bar while resolving.
- **Row 2**: 20px monospace filename in pure white.
- **Row 3**: 12px secondary folder path, truncated from the left with `…/`.
- **Row 4**: Warning badge `⚠ [count]` when `unresolved_import_count > 0`.
- **Binary/Media Files**: Centered icon glyph with a clear "No preview available" notice.

---

## 4. Import Graph Extraction & Honest Static Analysis (`apps/api/services/import_graph.py`)

- Extracted via tree-sitter AST queries without running untrusted code.
- Resolves:
  - TypeScript, TSX, JavaScript (`import`, `require`, dynamic `import()`, `tsconfig.json` paths)
  - Python (`from . import ...`, absolute package imports)
  - Go (`import "package"`, internal module directories)
  - Rust (`use crate::...`, internal submodules)
  - Java, C/C++, Ruby, PHP, and web configuration files
- **Honesty Guarantees**:
  - Dynamic imports `import(expr)` and unresolvable internal specifiers are recorded as `unresolved_specifiers` on the card and never drawn as dangling edges to nowhere.
  - External 3rd-party packages are deliberately omitted so the graph represents the repository itself.

---

## 5. Live Breakage Overlay

When a breaking dependency change ripples through the codebase:
- Files implicated in active incidents light up with a red border (`#E11D48`) and emissive glow.
- Import wires touching broken nodes switch to red severed status (`#E11D48`).
- All active broken files illuminate simultaneously.
- When an incident resolves via PR merge or fix, the graph smoothly transitions back to resting state.

---

## 6. Bridging Package Watching and LLM Healing

Repo Atlas plays a vital role across Telex's core loop:
1. **Watches Packages (`poll_registry`)**: Telex monitors npm and PyPI for new versions and breaking symbol changes.
2. **Maps Blast Radius (`/dashboard/atlas`)**: Repo Atlas locates the call sites and visualizes the complete blast radius and transitive import dependencies in 3D.
3. **Calls LLM for Fix (`generate_patch`)**: Telex feeds isolated AST syntax node snippets into the LLM (Gemini/Claude) to synthesize unified diffs.
4. **Verifies in CI (`validate_patch`)**: The patch runs against the repo's actual test suites in an isolated sandbox.
5. **Pre-Merge 3D Inspection**: Operators can click through the 3D cards on `/dashboard/atlas` to verify that the repair cleanly isolates the breakage before merging the PR.
