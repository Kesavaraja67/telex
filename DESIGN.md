# Telex Design System & Architectural Aesthetics

> **Source of Truth**: Visual language, material shaders, 3D spatial layout, typography, and telemetry tokens for Telex and Repo Atlas.

---

## 1. Aesthetic Identity: Hybrid — Industrial Hardware Surrounds Dark Void

### The Core Direction

Telex is **hybrid skeuomorphic**: dark 3D environments (Repo Atlas graph, landing robot) are framed by **machined metal control surfaces** — bezels, instrument panels, physical controls, and LED lamps that feel like they belong in a server rack or industrial control room.

**Two modes, strict separation:**

| Zone | Material | Rule |
|------|----------|------|
| 3D canvas (Atlas, landing) | Three.js scene with physical materials | Handled by 3D doctrine below — unchanged |
| 2D chrome (dashboard, sidebar, pages, HUD) | Metal bezels, anodized panels, key-cap buttons, LEDs | Governed by Phase 1 material tokens |

**What is NOT the design direction:**
- Generic dark SaaS with purple gradients → no
- Flat-cyber with glowing grid blobs → no
- Glassmorphism frosted cards everywhere → no
- Plain flat dark with no physical depth → no

**What IS the design direction:**
- Machined dark metal outer chassis (`--metal-*` tokens)
- Anodized matte panel insets for content wells (`--panel-*` tokens)
- Black glass recessed screens for 3D canvases (`--glass-*` tokens)
- Rubberized key-cap primary action buttons (`--key-*` tokens)
- LED signal lamps as the ONLY colored elements in 2D chrome (`--led-*` tokens)

---

## 2. Phase 1 Material System

### 2.1 Light Model

Single virtual light source: **top-left, 35° elevation**.

All bevels, insets, and shadows derive from these anchors — **do not invent box-shadows that contradict this light direction**:

| Token | Value | Meaning |
|-------|-------|---------|
| `--skeuo-light-angle` | `145deg` | Shadow direction (bottom-right) |
| `--skeuo-highlight-top` | `rgba(255,255,255,0.18)` | Bright lit edge (top-left) |
| `--skeuo-highlight-sub` | `rgba(255,255,255,0.07)` | Subtle lit side |
| `--skeuo-shadow-deep` | `rgba(0,0,0,0.65)` | Dark edge (bottom-right) |
| `--skeuo-shadow-mid` | `rgba(0,0,0,0.35)` | Soft shadow side |
| `--skeuo-shadow-inner` | `rgba(0,0,0,0.50)` | Recessed inset well |

### 2.2 Materials

#### Brushed Dark Metal (chassis, bezels)
- Tokens: `--metal-base`, `--metal-mid`, `--metal-light`, `--metal-shine`, `--metal-scratch`
- CSS class: `.metal-bezel`
- Has: linear scratch texture + lit top-left bevel + drop shadow

#### Matte Anodized Panel (content wells, sidebar)
- Tokens: `--panel-base`, `--panel-inset`, `--panel-rim`
- CSS class: `.panel-inset`
- Has: recessed inner shadow + dark top border + lit bottom rim

#### Recessed Black Glass (3D canvas frame, modal backs)
- Tokens: `--glass-base`, `--glass-rim-lit`, `--glass-rim-dark`, `--glass-inner-shadow`
- CSS class: `.glass-bezel`
- Has: very deep inset shadow + lit top rim + dark side/bottom rims

#### Rubberized Key-Cap (primary action buttons)
- Tokens: `--key-base`, `--key-top`, `--key-pressed`, `--key-label`
- CSS class: `.key-cap`
- Has: raised depth shadow (2px below chassis) + top-left bevel + pressed state (1px translateY)

### 2.3 Controls

| Control | Class / Pattern | States |
|---------|----------------|--------|
| Tactile button | `.key-cap` | rest / hover / pressed / disabled |
| Toggle switch | `.toggle-track` + `.toggle-thumb` + `.toggle-led` | off / on / disabled |
| LED lamp | `.led` + `data-state` attr | off / ok / warn / fault / busy |
| Engraved label | `.label-engraved` | static |
| Embossed label | `.label-embossed` | static |
| Engraved divider | `.divider-engraved` | static |

### 2.4 Color — LED-Only Color Policy

Color in Telex 2D chrome is **structurally restricted**:

| Token | Value | Permitted use |
|-------|-------|---------------|
| `--led-off` | `#1a1c1f` | LED off state |
| `--led-ok` | `#14b8a6` | LED ok state only (and Atlas wires — same color intentionally) |
| `--led-warn` | `#f59e0b` | LED warn state only |
| `--led-fault` | `#f43f5e` | LED fault state only |
| `--led-busy` | `#ffffff` | LED busy pulse only |

**Hard rules:**
- LED colors (`--led-ok`, `--led-warn`, `--led-fault`) must NEVER appear in: buttons, badges, progress bars, status pills, skeleton loaders, or any non-LED element.
- `rgba(79, 209, 197, *)` is banned from `RadialButton` and all 2D chrome — this was a legacy violation, now corrected.
- `--led-ok` and Atlas `--wire-healthy-core` (`#14b8a6`) share the same teal by design — one physical, one digital.

### 2.5 Motion

| Interaction | Duration | Easing token |
|-------------|----------|-------------|
| Button press travel | 80ms down, 120ms return | `--ease-press` / `--ease-spring` |
| LED fade on/off | 200ms | `ease-out` |
| Toggle slide | 150ms | `--ease-press` |
| `prefers-reduced-motion` | all transitions: `none` | — |

### 2.6 Typography (2D Chrome — No New Fonts)

Fonts remain: **Space Grotesk** (sans) and **Geist Mono** (mono).

| Class | Effect | Use |
|-------|--------|-----|
| `.label-engraved` | Recessed text (cut into metal) | Field labels, section headers |
| `.label-embossed` | Raised text (stamped) | Card titles, repo names |
| `.divider-engraved` | Recessed horizontal rule | Section separators |

---

## 3. Color Palette & Telemetry Tokens (3D Atlas Only)

> These govern the **3D scene materials**. They are not for 2D chrome.

| Token | Hex | Role |
|---|---|---|
| `--color-void` | `#050508` | Canvas background void |
| `--color-surface-card` | `#0f1117` | 3D File Card base surface |
| `--color-surface-border` | `#1e2430` | Card rim definition |
| `--color-text-primary` | `#f4f4f5` | File names, headers |
| `--color-text-secondary` | `#a1a1aa` | Folder labels, active badges |
| `--color-text-muted` | `#7e7e8a` | Metadata, paths, line counts |
| `--wire-healthy-jacket` | `#0f766e` | Healthy import cable jacket |
| `--wire-healthy-core` | `#14b8a6` | Healthy cable emissive core |
| `--wire-broken-jacket` | `#be123c` | Severed import cable jacket |
| `--wire-broken-core` | `#f43f5e` | Severed cable emissive core |
| `--pulse-photon-lead` | `#5eead4` | Lead data packet bead |
| `--status-warning` | `#f59e0b` | Incident pending / triage |

---

## 4. Typography Hierarchy

### Type Roles
1. **Telemetry & Code (Monospace)**:
   - Font: `Geist Mono`, `ui-monospace`, `SFMono-Regular`, `monospace`
   - Weight: Regular (`400`) & Medium (`500`)
   - Usage: File names, import paths, git commit SHAs, line numbers, breakage counts.

2. **Interface & Controls (Sans-Serif)**:
   - Font: `Space Grotesk`, `system-ui`, `-apple-system`, `sans-serif`
   - Usage: HUD action buttons, navigation tabs, modal headers, filter search.

---

## 5. 3D Spatial Layout & Physics Doctrine

### Hierarchy & Coordinate System
- **Y-Axis (Depth)**: Inverted layer depth (`y = -depth * LAYER_SPACING`).
  - Standard spacing: `4.8` units between folder tree generations.
- **X/Z-Axis (Layer Floor)**:
  - Folders anchor via deterministic polar distribution: `radius = 4.8 + 0.85 * siblingCount`.
  - File rings around folder anchors: `ringRadius = Math.max(2.6, Math.ceil(Math.sqrt(fileCount)) * 1.6)`.
  - Collision buffer: `1.75` force-collide clearance.

### Cable Physics (Flexible Rubber Catenary)
- **Normal Cable Radius**: `0.028` units.
- **Broken Cable Radius**: `0.044` units.
- **Inter-layer Connections**: Natural gravitational drape.
- **Intra-layer Connections**: Soft flexible upward arch.

### Elastic Card Interaction (Spring Physics)
- When grabbed, cards lift along the normal axis (`+0.38` units).
- On release, spring back via critically-damped harmonic oscillators (`Spring3`, stiffness `175`, damping `18`).

---

## 6. Lighting & Post-Processing Pipeline

- **Studio Key Light**: Directional white (`intensity: 1.2`, position: `(15, 25, 20)`).
- **Cool Fill Light**: Subtle cyan tint (`intensity: 0.4`, position: `(-15, 10, -15)`).
- **Studio Rim Light**: Directional backlight (`intensity: 0.6`, position: `(0, -20, -20)`).
- **PMREM Environment Map**: Softbox studio cubemap baked once at init.
- **UnrealBloomPass**: Selective glow on emissive cores (`threshold: 0.65`, `strength: 0.82`, `radius: 0.45`).
- **Atmospheric Fog**: `THREE.FogExp2` with density derived from graph bounding radius (Phase 3 fix — see spec).

---

## 7. Visual Consistency Rules

### Pure Monochrome 2D Chrome
- All 2D chrome (headers, dropdowns, HUD bars, cards, modals) follows the metal material system: `--metal-*`, `--panel-*`, `--glass-*`, `--key-*`, `--skeuo-*`.
- LED colors (`--led-*`) are the ONLY color permitted in 2D chrome, and only on `.led` elements.
- Zero generic SaaS gradients, no decorative blobs, no nested glass cards, no meaningless cosmetic chips.

### Wire-Teal Restriction
- `#5EEAD4` / `#14B8A6` / `#0f766e` are reserved for 3D cables and `.led[data-state="ok"]` only.
- Any other use is a violation.

### Consistent Loading States
- No gimmicky sci-fi HUDs. Use: `w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin`.
- 3D canvas: never unlit/black during loading. Always show loading state.

### Anti-Slop Guarantee
- Every visual element communicates state, hierarchy, or data flow.
- No decoration for its own sake.

---

## 8. Run Analysis Analog Dial & Physical Instrument Cluster

The Run Analysis interface (`RunAnalysisCard.tsx`) applies the hybrid skeuomorphic design doctrine to analytical risk telemetry:

### 8.1 Physical Meter Face & Needle Geometry
- **Outer Bezel**: Machined aluminum bezel with concentric bevels (`.metal-bezel`, `145deg` light highlight).
- **Recessed Face**: Inset dark matte well (`--panel-inset`) textured with radial tick indicators and calibrated numeric stops (0, 25, 50, 75, 100).
- **Mechanical Needle**:
  - Center hub: Machined brass/metal pivot rivet with rim reflection.
  - Needle blade: Tapered high-contrast needle with drop shadow offset along the virtual light axis.
  - Deflection angle: Linearly mapped across a $260^\circ$ total sweep:
    $$\theta = -130^\circ + \left(\frac{\text{Score}}{100}\right) \times 260^\circ$$
  - Spring dampening: 700ms cubic-bezier transition (`cubic-bezier(0.34, 1.3, 0.64, 1)`), simulating physical galvanometer needle inertia and spring settle.

### 8.2 Sub-Gauge Instrumentation
- Four calibrated horizontal sub-score gauges (Structure, Dependency, Change Safety, Verification).
- **Physical Inset Wells**: Deep engraved channels with top shadow (`--skeuo-shadow-inner`).
- **Graceful Unmeasured State**: When repository telemetry is insufficient to compute a sub-score (e.g. no CI history), the gauge renders a brushed cross-hatch channel stamped with `"NOT MEASURED"`, preventing misleading zeros.

### 8.3 Severity Lamps & 3D Spatial Deep-Linking
- Findings cards feature physical circular LED indicators:
  - Critical severity: Crimson pulse (`--led-fault`)
  - Warning severity: Amber glow (`--led-warn`)
  - Informational severity: White/teal illumination
- **Spatial Telemetry Linkage**: Every finding includes a physical key-cap button deep-linking directly into `/dashboard/atlas?focus=<path>`, animating the 3D camera rig directly to the implicated AST node.

