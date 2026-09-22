# Repo Atlas — 3D Full-Repo Structural Code Visualizer

Repo Atlas renders a persistent, whole-repository 3D structural map of any connected codebase in Telex. It organizes files into hierarchical horizontal layers mirroring folder depth, with physical 3D cards, real statically-extracted import wires, interactive drag physics, on-demand code reading, and an active incident breakage overlay.

---

## 1. Architecture Overview

```
apps/web/app/dashboard/repos/[id]/atlas/page.tsx
  └─ AtlasView.tsx (HUD, polling, SSE event handling)
       ├─ AtlasScene.ts (Three.js scene, lighting, camera orbit)
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
  - Relative imports (`./`, `../`)
  - Path aliases from `tsconfig.json` (`compilerOptions.paths`)
  - Python module imports
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
