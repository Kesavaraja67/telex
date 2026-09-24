<a id="top"></a>

<div align="center">

  <h1>Repo Atlas 3D Engine</h1>
  <p><b>Spatial Architecture Visualizer, Catenary Conduit Physics & Blast Radius Mapping</b></p>

  <p>
    <img src="https://img.shields.io/badge/Three.js-WebGL-000000?style=flat-square&logo=three.js&logoColor=white" alt="Three.js WebGL" />
    <img src="https://img.shields.io/badge/d3--force--3d-Layered%20Physics-F9A03F?style=flat-square&logoColor=white" alt="d3-force-3d" />
    <img src="https://img.shields.io/badge/AST%20Imports-Multi--Language-14B8A6?style=flat-square" alt="Multi-Language AST Imports" />
    <img src="https://img.shields.io/badge/SSE-Realtime%20Incidents-F43F5E?style=flat-square" alt="Realtime SSE Incidents" />
  </p>

  <br>

  <p>
    <a href="#overview"><b>Overview</b></a> &nbsp;•&nbsp;
    <a href="#component-architecture"><b>Architecture</b></a> &nbsp;•&nbsp;
    <a href="#layered-layout-math"><b>Layout Mathematics</b></a> &nbsp;•&nbsp;
    <a href="#catenary-cables"><b>Catenary Cables</b></a> &nbsp;•&nbsp;
    <a href="#card-textures"><b>Card Textures</b></a> &nbsp;•&nbsp;
    <a href="#incident-overlay"><b>Incident Overlay</b></a>
  </p>

</div>

<br>

---

<br>

## <a id="overview"></a>01. Overview

Repo Atlas is Telex's dedicated 3D architectural visualizer and blast radius intelligence engine. Rather than rendering flat, static directory trees, Repo Atlas constructs an interactive spatial reactor room for any connected repository.

When upstream packages release breaking changes, operators can immediately trace how internal modules depend on the affected package, inspect source code in-canvas, and verify patch isolation before merging.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="component-architecture"></a>02. Component Architecture

```text
apps/web/app/dashboard/atlas/page.tsx (Operator page with universal repo switcher)
  └── AtlasView.tsx                   (HUD, search filter, SSE event listener, keybindings)
       ├── AtlasScene.ts              (Three.js scene graph, PMREM lighting, camera orbit)
       │    ├── LayeredLayout.ts      (Hierarchical depth Y + 2D polar force simulation)
       │    ├── CardTextureAtlas.ts   (512x320 canvas card textures & language badges)
       │    ├── WireRenderer2.ts      (Catenary 3D cables + bezier import wires + photon pulses)
       │    ├── DragController.ts     (Raycasting + horizontal plane drag constraint)
       │    └── lastEditedCache.ts    (Lazy debounced commit metadata fetching)
       └── CodePreviewPanel.tsx       (Slide-in syntax-highlighted code reader + breakage banner)
```

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="layered-layout-math"></a>03. Layered Layout Mathematics (`LayeredLayout.ts`)

To avoid chaotic ball-of-mud graph clustering, Repo Atlas employs a deterministic **layered polar layout**:

### 1. Depth Axis Stratification ($Y$)
Directory hierarchy is strictly mapped to the negative vertical axis:
$$Y = -\text{depth} \times \text{LAYER\_SPACING} \quad (\text{where } \text{LAYER\_SPACING} = 4.8)$$
- Root files and top-level modules reside at $Y = 0$.
- Submodules and internal libraries descend downward without overlapping vertical planes.
- $Y$ coordinates are locked during force simulation, preserving architectural hierarchy.

### 2. Deterministic Polar Folder Anchors ($X, Z$)
Sibling folders at the same depth level are distributed along concentric polar rings:
$$\text{radius} = 4.8 + 0.85 \times \text{siblingCount}$$
$$\theta_i = \theta_{\text{parent}} + \frac{2\pi \cdot i}{\text{siblingCount}}$$

### 3. File Card Ring Seeding & Collision Avoidance
Individual files cluster around their folder anchor:
$$\text{ringRadius} = \max\left(2.6, \lceil\sqrt{\text{fileCount}}\rceil \times 1.6\right)$$

A constrained 2D force simulation (`d3-force-3d`) runs along the $X$ and $Z$ axes with `forceCollide(1.75)` to eliminate card overlap while strictly preserving $Y$ coordinates.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="catenary-cables"></a>04. Catenary Conduit Physics & Photon Pulses

Imports are modeled as physical dielectric rubber cables carrying optical data packets:

```text
               (p1)                                     (p2)
                ┌────────┐                             ┌────────┐
                │ Card A │                             │ Card B │
                └────┬───┘                             └───┬────┘
                     │                                     │
                     ╰──────╮                       ╭──────╯
                            ╰───────────────╮       │
                                    • • •   ╰───────╯
                                 [photon pulse]
```

### Physics Specification
- **Gravitational Sag**: Inter-layer cables sag under simulated gravity:
  $$\text{mid}_y = \frac{p1_y + p2_y}{2} - \text{sag}$$
- **Intra-layer Upward Arches**: Connections on the same depth layer arch upward gracefully to avoid colliding with card surfaces:
  $$\text{mid}_y += \min(1.8, \max(0.35, \text{distance} \times 0.15))$$
- **Normal Cable Geometry**: $r = 0.028$ units, PBR roughness `0.42`, teal emissive core (`#14B8A6`).
- **Severed Cable Geometry**: $r = 0.044$ units, crimson emissive core (`#F43F5E`).
- **Photon Packet Simulation**: High-luminance emissive beads (`#5EEAD4`) travel along bezier curves representing active data calls.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="card-textures"></a>05. Canvas Card Texture Atlas (`CardTextureAtlas.ts`)

Each 3D file card is a 16:10 world plane (`1.6 × 1.0` units) backed by an optimized 512×320 dynamic canvas texture:

- **Frosted Polycarbonate Base**: `rgba(255, 255, 255, 0.03)` with 1px border.
- **Language Chips**: Pre-rendered badge chips for `TS`, `TSX`, `JS`, `PY`, `GO`, `RS`, `JAVA`, `C++`, `MD`.
- **Monospace Typography**: File names rasterized in JetBrains Mono / Geist Mono for tabular stability.
- **Git Metadata**: Displays relative last-edited timestamps (`2h ago`, `3d ago`) or skeleton bars while resolving.
- **Incident State**: Broken cards render with a high-contrast crimson border (`#E11D48`) and emissive halo.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="incident-overlay"></a>06. Live Incident Breakage Overlay (SSE)

Repo Atlas connects to the backend incident event stream:
```typescript
const eventSource = new EventSource(`/api/repos/${repoId}/incidents/stream`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.broken_files: string[]
  // data.severed_wires: [string, string][]
  highlightIncidentBlastRadius(data);
};
```

1. **Instant Propagation**: When a package breaking change is detected, all implicated source files transition into active crimson alert.
2. **Severed Conduits**: Dependent import wires flash and switch to crimson warning state.
3. **Smooth Resolution**: When a repair patch is merged and verified, the affected nodes and cables elastically transition back to healthy teal resting state.

<br>

<div align="center">
  <a href="#top">
    <img src="https://img.shields.io/badge/%E2%86%91-Back%20to%20Top-050508?style=flat-square&logoColor=white" alt="Back to Top" />
  </a>
</div>
