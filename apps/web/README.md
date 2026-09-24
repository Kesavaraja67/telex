<a id="top"></a>

<div align="center">

  <h1>Telex Web Interface</h1>
  <p><b>Next.js 16 Web Application, 3D WebGL Bot & Real-Time Telemetry Dashboard</b></p>

  <p>
    <img src="https://img.shields.io/badge/Next.js-16-050508?style=flat-square&logo=next.js&logoColor=white" alt="Next.js 16" />
    <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React 19" />
    <img src="https://img.shields.io/badge/Three.js-WebGL-000000?style=flat-square&logo=three.js&logoColor=white" alt="Three.js" />
    <img src="https://img.shields.io/badge/Tailwind-CSS%204-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white" alt="Tailwind CSS 4" />
    <img src="https://img.shields.io/badge/TypeScript-Strict-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript Strict" />
  </p>

  <br>

  <p>
    <a href="#overview"><b>Overview</b></a> &nbsp;•&nbsp;
    <a href="#design-system"><b>Design System</b></a> &nbsp;•&nbsp;
    <a href="#core-routes"><b>Routes & Views</b></a> &nbsp;•&nbsp;
    <a href="#threejs-atlas"><b>3D Graphics & Physics</b></a> &nbsp;•&nbsp;
    <a href="#local-development"><b>Local Setup</b></a> &nbsp;•&nbsp;
    <a href="#deployment"><b>Deployment</b></a>
  </p>

</div>

<br>

---

<br>

## <a id="overview"></a>01. Overview

The `apps/web` application serves as both the public marketing interface and the primary operator cockpit for Telex. Built on Next.js 16 (App Router), it provides:
- **Repo Atlas (`/dashboard/atlas`)**: An interactive 3D spatial visualizer rendering repository import graphs, module hierarchy, and real-time failure cascades.
- **Fleet Cockpit (`/dashboard`)**: Unified telemetry displaying active package monitors, verified patches, and pending human-reviewed PRs.
- **Repository Management (`/dashboard/repos`)**: Per-repository tracking toggles and CI verification policy settings (`requires_tests`, `requires_typecheck`).
- **Interactive Marketing Surface (`/`)**: High-contrast monochrome landing page featuring an interactive WebGL 3D bot (`TelexBot3D.tsx`), live pipeline marquee, and ticket feed.
- **Cross-Domain Session Authentication**: HttpOnly token validation ensuring seamless state persistence between Vercel web edge and Render backend.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="design-system"></a>02. Design System & Aesthetic Doctrine

The interface strictly implements Telex's **Monochrome Cybernetic Hardware** doctrine defined in [`DESIGN.md`](../../DESIGN.md):

| Token | Value | Role in Web Interface |
|---|---|---|
| `--void` | `#000000` / `#050508` | Background void canvas with subtle depth fog |
| `--surface-base` | `rgba(255, 255, 255, 0.03)` | Frosted glass cards and navigation backdrops |
| `--surface-raised` | `rgba(255, 255, 255, 0.06)` | Elevated popovers, dropdowns, and modals |
| `--text-pure` | `#FFFFFF` | Primary headers, active links, and titles |
| `--text-secondary` | `#A1A1AA` | Subtitles, labels, and secondary badges |
| `--text-muted` | `#7E7E8A` | File paths, commit SHAs, and timestamp metadata |
| `--border` | `rgba(255, 255, 255, 0.12)` | Hairline container borders |
| `--wire-cyan` | `#14B8A6` / `#5EEAD4` | **Strictly reserved for 3D data wires & photon pulses** |
| `--wire-crimson` | `#F43F5E` / `#E11D48` | **Strictly reserved for severed lines & breaking incidents** |

> **Monochrome Rule**: In accordance with Telex's design principles, color is never used decoratively on 2D UI chrome. Cyan and crimson are strictly reserved for 3D data cables and incident indicators.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="core-routes"></a>03. Core Routes & Views

```text
apps/web/app/
├── page.tsx                    # Landing page (Hero, 3D Bot, Marquee, Live Feed)
└── dashboard/
    ├── page.tsx                # Fleet overview & telemetry counter
    ├── repos/
    │   ├── page.tsx            # Connected repository catalog & tracking toggles
    │   └── [id]/page.tsx       # Per-repo change history, diff viewer & patch logs
    ├── atlas/
    │   └── page.tsx            # Dedicated 3D Repo Atlas with repository switcher
    ├── settings/
    │   └── page.tsx            # BYOK provider key manager (10 LLMs) & CI gates
    └── activity/
        └── page.tsx            # Reverse-chronological audit & event feed
```

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="threejs-atlas"></a>04. 3D Graphics & Physics Subsystems

### 1. Interactive 3D Bot (`components/marketing/TelexBot3D.tsx`)
Rendered on the landing page hero using Three.js with custom shader materials, ambient floating oscillations, eye-tracking cursor responsiveness, and metallic polycarbonate rim reflections.

### 2. Repo Atlas 3D Visualizer (`components/atlas/`)
- **`AtlasScene.ts`**: Initializes Three.js WebGL canvas, PMREM softbox studio lighting, camera orbit controls, and smooth focus tweens.
- **`LayeredLayout.ts`**: Stratifies folder tree depth along the $Y$ axis ($Y = -\text{depth} \times 4.8$), distributing sibling directories along polar coordinate rings.
- **`CardTextureAtlas.ts`**: Generates crisp 512×320 canvas textures for file cards, including language badges (`TS`, `PY`, `GO`, `RS`), commit metadata, and warning icons.
- **`WireRenderer2.ts`**: Draws 3D catenary curves with physical gravity sag, traveling photon beads, and crimson incident breakage states.
- **`CodePreviewPanel.tsx`**: Slide-in syntax-highlighted source code reader with breakage diagnostic banners.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="local-development"></a>05. Local Development

### 1. Install Dependencies
```bash
npm install
```

### 2. Environment Variables
Copy `.env.example` to `.env.local`:
```bash
cp .env.example .env.local
```

Configure:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GITHUB_APP_NAME=telex-agent-dev
```

### 3. Launch Development Server
```bash
npm run dev
```

*Note for Windows users*: If Turbopack native binary encounters file-lock restrictions, run with Webpack:
```bash
npm run dev -- --webpack
```

Open `http://localhost:3000` in your browser.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="deployment"></a>06. Production Deployment

The web application is optimized for deployment on Vercel:

```bash
# Build production bundle
npm run build

# Start production server
npm run start
```

Ensure `NEXT_PUBLIC_API_URL` is configured in your Vercel project settings to route API requests to your production backend.

<br>

<div align="center">
  <a href="#top">
    <img src="https://img.shields.io/badge/%E2%86%91-Back%20to%20Top-050508?style=flat-square&logoColor=white" alt="Back to Top" />
  </a>
</div>
