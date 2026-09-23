# Telex Design System & Architectural Aesthetics

> **Source of Truth**: Visual language, material shaders, 3D spatial layout, typography, and telemetry tokens for Telex and Repo Atlas.

---

## 1. Aesthetic Identity: Industrial Cybernetic Hardware

### The Core Metaphor
Repo Atlas is an **interactive architectural reactor room** for production codebases. Looking at your repository should feel like stepping inside an illuminated, physical computing system:
- **Dielectric Rubber Cables**: Imports are physical conduits carrying live photon data pulses. They have mass, flexibility, and gravitational sag.
- **Floating Polycarbonate Cards**: Code modules float as frosted, precision-etched instrument cards casting soft ambient contact shadows.
- **The Void**: Pure receding atmospheric depth (`#050508` void with soft depth fog) ensuring high-contrast telemetry visibility from any orbit angle.
- **Strict Anti-Slop Guarantee**: Zero generic purple SaaS gradients, zero decorative floating blobs, zero nested card boxes, and zero meaningless cosmetic chips. Every visual element communicates state, hierarchy, or data flow.

---

## 2. Color Palette & Telemetry Tokens

### Color Philosophy
Color in Repo Atlas is **rare, purposeful, and communicative**. Neutral dark void surrounds the scene; color strictly signals system health, active data flow, and architectural boundaries.

| Token | Hex | Role | Contrast / Luminance |
|---|---|---|---|
| `--color-void` | `#050508` | Canvas background void | 0% ambient baseline |
| `--color-surface-card` | `#0f1117` | 3D File Card base surface | Low-reflectance polycarbonate |
| `--color-surface-border` | `#1e2430` | Card rim definition | Clean structural perimeter |
| `--color-text-primary` | `#f4f4f5` | File names, major headers | > 14:1 against void (AAA) |
| `--color-text-secondary` | `#a1a1aa` | Folder labels, active badges | > 7:1 against card surface (AAA) |
| `--color-text-muted` | `#7e7e8a` | Metadata, paths, line counts | > 4.65:1 against void (WCAG AA) |
| `--wire-healthy-jacket` | `#0f766e` | Healthy import cable jacket | PBR roughness 0.42, metalness 0.1 |
| `--wire-healthy-core` | `#14b8a6` | Healthy cable emissive core | Luminous cyan accent |
| `--wire-broken-jacket` | `#be123c` | Severed import cable jacket | PBR roughness 0.38, clearcoat 0.4 |
| `--wire-broken-core` | `#f43f5e` | Severed cable emissive core | Active crimson warning |
| `--pulse-photon-lead` | `#5eead4` | Lead data packet bead | High bloom saturation (threshold 0.65) |
| `--status-warning` | `#f59e0b` | Incident pending / triage | High-visibility amber |

---

## 3. Typography Hierarchy

### Type Roles
1. **Telemetry & Code (Monospace)**:
   - Font: `JetBrains Mono`, `ui-monospace`, `SFMono-Regular`, `monospace`
   - Weight: Regular (`400`) & Medium (`500`)
   - Usage: File names, import paths, git commit SHAs, line numbers, breakage counts.
   - Principle: Numeric data and code symbols must align tabularly without proportional jitter.
2. **Interface & Controls (Sans-Serif)**:
   - Font: `Inter`, `system-ui`, `-apple-system`, `sans-serif`
   - Usage: HUD action buttons, navigation tabs, modal headers, filter search.
   - Principle: Neutral, highly legible at micro-sizes (11px–13px) with subtle letter-spacing (`+0.02em`).

---

## 4. 3D Spatial Layout & Physics Doctrine

### Hierarchy & Coordinate System
- **Y-Axis (Depth)**: Inverted layer depth (`y = -depth * LAYER_SPACING`).
  - Standard spacing: `4.8` units between folder tree generations.
  - Ensures clean vertical parallax without card stacking.
- **X/Z-Axis (Layer Floor)**:
  - Folders anchor via deterministic polar distribution: `radius = 4.8 + 0.85 * siblingCount`.
  - File rings around folder anchors: `ringRadius = Math.max(2.6, Math.ceil(Math.sqrt(fileCount)) * 1.6)`.
  - Collision buffer: `1.75` force-collide clearance (cards are `1.6 x 1.0`), preventing card or label overlap.

### Cable Physics (Flexible Rubber Catenary)
- **Normal Cable Radius**: `0.028` units (substantial, rounded 3D cylinder).
- **Broken Cable Radius**: `0.044` units.
- **Inter-layer Connections**: Natural gravitational drape (`mid.y = (p1.y + p2.y) * 0.5 - sag`).
- **Intra-layer Connections**: Soft flexible upward arch (`mid.y += Math.min(1.8, Math.max(0.35, dist * 0.15))`).

### Elastic Card Interaction (Spring Physics)
- When grabbed, cards lift along the normal axis (`+0.38` units) with dynamic contact shadows.
- Dragging stretches connected rubber cables in real-time.
- On release, cards elastically spring back to `(baseX, baseZ)` via critically-damped harmonic oscillators (`Spring3`, stiffness `175`, damping `18`).
- Attached rubber cables recoil dynamically until the card settles into its resting slot.

---

## 5. Lighting & Post-Processing Pipeline

- **Studio Key Light**: Directional white (`intensity: 1.2`, position: `(15, 25, 20)`).
- **Cool Fill Light**: Subtle cyan tint (`intensity: 0.4`, position: `(-15, 10, -15)`).
- **Studio Rim Light**: Directional backlight (`intensity: 0.6`, position: `(0, -20, -20)`).
- **PMREM Environment Map**: Softbox studio cubemap baked once at init for realistic micro-reflections.
- **UnrealBloomPass**: Selective glow on emissive cores (`threshold: 0.65`, `strength: 0.82`, `radius: 0.45`).
- **Atmospheric Fog**: `THREE.FogExp2(0x000000, 0.018)` for organic depth falloff.

---

## 6. Visual Consistency & Loading Doctrine

### Pure Monochrome Consistency & Wire-Only Color Policy
Color discipline in Repo Atlas is absolute:
- **Cyan/Teal Wire-Only Policy**: The cyan/teal data color (`#5EEAD4` / `#14B8A6`) is **strictly reserved for the physical 3D graph cables and live photon pulses**. It must never appear in 2D UI chrome, buttons, badges, status pills, or loaders.
- **Pure Monochrome UI Chrome**: All 2D headers, dropdowns, HUD navigation bars, cards, and modal panels strictly follow Telex's pure monochrome engineering system (pure white `#FFFFFF`, zinc `#A1A1AA`, muted `#7E7E8A`, void black `#000000`).
- **Consistent Loading States**:
  - No gimmicky or fake sci-fi HUDs. Loading states must be clean, minimal, and 100% consistent with the rest of the Telex dashboard (`w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin`).
  - **Zero Unlit Voids**: The 3D canvas must never sit in an unlit pitch-black state. During initial graph fetch (`state.kind === "idle"`) and during computation (`state.kind === "computing"`), the loading indicator is always active and displays clear diagnostic text (`Loading graph architecture…` / `Computing graph layout…`).

