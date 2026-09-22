# Telex Web — Autonomous Dependency Healing Portal & Dashboard

> **Next.js 16 Web App, Interactive 3D Bot, and Real-Time Telemetry Dashboard**

---

## Overview

The `apps/web` application is the unified operator dashboard and marketing portal for Telex. It features:
- **Repository Management (`/dashboard/repos`)**: Overview of connected repositories, active tracking status, and verification policy toggles (`requires_tests`, `requires_typecheck`).
- **Telemetry Dashboard (`/dashboard`)**: Real-time stats on monitored repositories, detected dependency breaks, generated patches, and open Pull Requests.
- **Interactive Marketing Experience (`/`)**: High-contrast monochrome landing page featuring an interactive 3D WebGL bot (`TelexBot3D.tsx`), animated pipeline marquee, and live patch feed demo (`TicketFeed.tsx`).
- **Cross-Origin Authentication (`Nav.tsx`)**: Asynchronous `/api/auth/me` session validation with HttpOnly tokens ensuring seamless login state display between Vercel and Render hosts.

---

## Core Routes & Views

| Route | Purpose | Key Components |
|---|---|---|
| `/` | Marketing landing page | `Hero.tsx`, `TelexBot3D.tsx`, `HowItWorks.tsx`, `LiveMarquee.tsx`, `TicketFeed.tsx`, `FreeStrip.tsx` |
| `/dashboard` | Operator analytics, patch counts, recent detected changes | `StatCounter.tsx`, `RepoCard.tsx`, `DiffViewer.tsx` |
| `/dashboard/repos` | Connected repositories, GitHub App installation status | `RepoCard.tsx`, `Badge.tsx` |
| `/dashboard/repos/[id]` | Repository detail view with active patches and verification status | `PatchTicket.tsx`, `DiffViewer.tsx` |
| `/dashboard/atlas` | Dedicated 3D Repo Atlas · AST dependency visualizer · real-time incident mapping | `AtlasView.tsx`, `AtlasScene.ts`, `LayeredLayout.ts`, `CardTextureAtlas.ts`, `CodePreviewPanel.tsx` |
| `/dashboard/settings` | Verification gate policies and provider key management | Policy toggles, provider status |
| `/dashboard/activity` | Live reverse-chronological event and audit feed | `ActivityFeed.tsx` |

---

## Technology Stack

- **Framework**: Next.js 16.3.1 (App Router)
- **Styling**: Tailwind CSS, Vanilla CSS design tokens, Glassmorphism
- **Animations**: Motion React (`motion/react`), Anime.js
- **3D Graphics & Physics**: Three.js WebGL Canvas, d3-force-3d layered spatial layout
- **Typography**: Space Grotesk, Plus Jakarta Sans, Geist Mono
- **Deployment**: Vercel

---

## Local Development

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env.local`:
```bash
cp .env.example .env.local
```

Ensure `NEXT_PUBLIC_API_URL` points to your API:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GITHUB_APP_NAME=telex-agent-dev
```

### 3. Start Development Server
```bash
npm run dev
# If Turbopack native binary is blocked on Windows:
# npm run dev -- --webpack
```
