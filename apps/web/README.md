# Telex Web — Live Revenue Recovery Portal & Dashboard

> **Next.js 16 (Turbopack), Three.js WebGL 3D Bot, Real-Time Telemetry Stream & Recovery Dashboard**  
> *Engineered for the Razorpay Pay 2026 Buildathon.*

---

## Overview

The `apps/web` application is the unified operator dashboard and public showcase for Telex. It features:
- **Live Recovery Stream (`/dashboard/recovery`)**: Real-time event feed tracking live payment failures, Tier-1/Tier-2 classification outcomes, bounded retry backoffs, and revenue recovered in ₹ paise.
- **Interactive Pipeline Visualizer (`RecoveryPipelineVisualizer.tsx`)**: Step-by-step visual audit trail displaying the full lifecycle of every failed payment from Razorpay ingestion to verified GitHub PR.
- **Batch Simulator**: Live control interface allowing evaluators to inject custom failure rates and watch the autonomous recovery pipeline react in real time.
- **3D WebGL Robot (`TelexBot3D.tsx`)**: Custom Three.js interactive 3D bot on the marketing page tracking user cursor movements at 60 FPS.
- **Illoca-Inspired Pure Monochrome Aesthetic**: Sleek, high-contrast dark mode with glassmorphism, kinetic scan lines, and micro-telemetry coordinates.

---

## Core Routes & Views

| Route | Purpose | Key Components |
|---|---|---|
| `/` | Marketing landing page for Razorpay Buildathon | `Hero.tsx`, `TelexBot3D.tsx`, `HowItWorks.tsx`, `LiveMarquee.tsx`, `TicketFeed.tsx`, `FreeStrip.tsx` |
| `/dashboard/recovery` | Live payment failure telemetry stream & batch tester | `RecoveryTicket.tsx`, `RecoveryPipelineVisualizer.tsx`, `StatCounter.tsx`, `TickerRibbon.tsx` |
| `/dashboard` | Operator analytics, honest recovery rate metrics, revenue totals | `StatCounter.tsx`, `RepoCard.tsx`, `DiffViewer.tsx` |
| `/dashboard/repos` | Connected repositories, GitHub App installation status | `RepoCard.tsx`, `Badge.tsx` |
| `/dashboard/settings` | Verification gate policies (require tests, typecheck enforcement) | Verification policy toggles, secret status |

---

## Technology Stack

- **Framework**: Next.js 16.3.1 (App Router + Turbopack)
- **Styling**: Tailwind CSS, Vanilla CSS design tokens, Glassmorphism
- **Animations**: Motion React (`motion/react`), Anime.js
- **3D Graphics**: Three.js WebGL Canvas
- **Typography**: Space Grotesk, Plus Jakarta Sans, Geist Mono
- **Deployment**: Vercel (`https://telex-pi.vercel.app`)

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

Ensure `NEXT_PUBLIC_API_URL` points to your local or deployed API:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GITHUB_APP_NAME=telex-agent-dev
```

### 3. Start Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) or [http://localhost:3000/dashboard/recovery](http://localhost:3000/dashboard/recovery).

### 4. Production Build Verification
```bash
npm run build
```
Compiled with zero TypeScript or bundling errors.
