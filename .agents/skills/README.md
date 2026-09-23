# Telex Product Engineering Skills Suite

This directory contains the full suite of specialized product engineering skills adapted from Garry Tan's [`gstack`](https://github.com/garrytan/gstack) and custom Telex workflows (like `/brag`).

Each skill is a self-contained, domain-specific AI capability with rigorous methodology, checklists, and execution doctrine.

---

## Skill Directory & Quick Reference

### 1. Product Discovery, Strategy & Inception
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`office-hours`](./office-hours/SKILL.md) | `/office-hours`, "brainstorm this", "is this worth building" | YC Office Hours: 6 forcing questions exposing demand reality, desperate specificity, and narrowest wedge. |
| [`plan-ceo-review`](./plan-ceo-review/SKILL.md) | `/plan-ceo-review`, "review this plan", "founder mode" | Strategic challenge with 4 scope modes: 10x ambition, narrow wedge, standard execution, or pivot. |
| [`spec`](./spec/SKILL.md) | `/spec`, "write a spec for this" | Five-phase executable specification writing: turns vague intent into a concrete engineering contract. |
| [`retro`](./retro/SKILL.md) | `/retro`, "weekly retro", "what shipped" | Engineering retrospective analyzing work patterns, velocity, code metrics, and post-mortems. |

### 2. Architecture & Technical Planning
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`plan-eng-review`](./plan-eng-review/SKILL.md) | `/plan-eng-review`, "architecture review" | Engineering manager mode: locks architecture, identifies failure modes, schema changes, scale, and testing strategy. |
| [`plan-design-review`](./plan-design-review/SKILL.md) | `/plan-design-review` | Designer's eye plan review: visual hierarchy, component reusability, anti-slop, and micro-interactions. |
| [`plan-devex-review`](./plan-devex-review/SKILL.md) | `/plan-devex-review` | Developer experience review: API ergonomics, ease of onboarding, SDK friction, and CLI usability. |
| [`plan-tune`](./plan-tune/SKILL.md) | `/plan-tune` | Self-tuning question sensitivity and developer psychographic alignment. |
| [`autoplan`](./autoplan/SKILL.md) | `/autoplan` | End-to-end multi-perspective planning pipeline through CEO, Eng, and Design review phases. |

### 3. Design, UI Excellence & Prototyping
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`design-consultation`](./design-consultation/SKILL.md) | `/design-consultation` | Researches aesthetic landscape, creates design tokens, typography, color palettes, and motion curves. |
| [`design-review`](./design-review/SKILL.md) | `/design-review` | Visual design QA: catches visual inconsistency, awkward spacing, hierarchy bugs, and AI slop. |
| [`design-shotgun`](./design-shotgun/SKILL.md) | `/design-shotgun` | Generates multiple distinct design variants and provides side-by-side comparison boards. |
| [`design-html`](./design-html/SKILL.md) | `/design-html` | Crafts production-grade HTML/CSS prototypes and interactive mockups. |
| [`diagram`](./diagram/SKILL.md) | `/diagram` | Generates system and sequence diagrams in SVG, PNG, and editable Excalidraw formats. |

### 4. Code Quality, Review & Root-Cause Debugging
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`review`](./review/SKILL.md) | `/review`, "review this PR" | Pre-landing code review: scans diffs for silent bugs, race conditions, edge cases, and performance regressions. |
| [`investigate`](./investigate/SKILL.md) | `/investigate`, "debug this", "why did this fail" | Scientific root-cause debugging: hypothesis tree, minimal reproduction, and isolation before patching. |
| [`health`](./health/SKILL.md) | `/health` | Codebase health dashboard: dead code, dependency drift, test coverage, and tech debt analysis. |
| [`devex-review`](./devex-review/SKILL.md) | `/devex-review` | Audit live developer experience, SDKs, and developer documentation. |

### 5. Quality Assurance & Browser Testing
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`qa`](./qa/SKILL.md) | `/qa <url>` | Systematic automated and interactive web QA: verifies user flows, finds regressions, and proposes fixes. |
| [`qa-only`](./qa-only/SKILL.md) | `/qa-only <url>` | Report-only QA testing pass without auto-modifying code. |
| [`browse`](./browse/SKILL.md) | `/browse <url>` | Full browser automation and page inspection with snapshot dropdowns. |
| [`open-gstack-browser`](./open-gstack-browser/SKILL.md) | `/open-gstack-browser` | Launches interactive browser session. |
| [`scrape`](./scrape/SKILL.md) | `/scrape <url>` | Targeted content and data extraction from live web pages. |
| [`setup-browser-cookies`](./setup-browser-cookies/SKILL.md) | `/setup-browser-cookies` | Imports cookies for authenticated browser sessions. |
| [`skillify`](./skillify/SKILL.md) | `/skillify` | Codifies successful browser flows into reusable permanent skills. |

### 6. Security & Safety Guardrails
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`cso`](./cso/SKILL.md) | `/cso`, "security audit" | Chief Security Officer: audits for OWASP Top 10, STRIDE threat modeling, access control flaws, and secrets. |
| [`careful`](./careful/SKILL.md) | `/careful` | Destructive command safety guardrails: intercepts high-risk commands and validates blast radius. |
| [`guard`](./guard/SKILL.md) | `/guard` | Combined safety mode: destructive command warnings + directory-scoped edit boundaries. |
| [`freeze`](./freeze/SKILL.md) | `/freeze <dir>` | Restricts edits strictly to designated directories for a session. |
| [`unfreeze`](./unfreeze/SKILL.md) | `/unfreeze` | Clears edit boundaries, restoring full repository edit capability. |

### 7. Release Engineering & Deployment
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`ship`](./ship/SKILL.md) | `/ship`, "ship this" | End-to-end release: branch safety, test validation, diff review, version bump, changelog update, and PR creation. |
| [`land-and-deploy`](./land-and-deploy/SKILL.md) | `/land-and-deploy` | Full landing and deploy workflow with post-deploy health checks. |
| [`landing-report`](./landing-report/SKILL.md) | `/landing-report` | Queue dashboard for workspace-aware shipping status. |
| [`canary`](./canary/SKILL.md) | `/canary` | Post-deploy canary monitoring and verification. |
| [`setup-deploy`](./setup-deploy/SKILL.md) | `/setup-deploy` | Configures deployment settings and environments for `/land-and-deploy`. |
| [`document-release`](./document-release/SKILL.md) | `/document-release` | Authors release notes and user-facing documentation for shipped features. |

### 8. Documentation, Marketing & Knowledge
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`brag`](./brag/SKILL.md) | `/brag`, "make a launch video" | Turns the current web project into a short, polished, shareable launch video using Hyperframes. |
| [`document-generate`](./document-generate/SKILL.md) | `/document-generate` | Generates missing architectural and API documentation from scratch. |
| [`make-pdf`](./make-pdf/SKILL.md) | `/make-pdf` | Compiles markdown design docs or specs into publication-quality PDFs. |
| [`codex`](./codex/SKILL.md) | `/codex` | Codex CLI integration and deep knowledge search. |
| [`learn`](./learn/SKILL.md) | `/learn` | Records and retrieves project learnings, edge cases, and hard-won patterns. |
| [`setup-gbrain`](./setup-gbrain/SKILL.md) | `/setup-gbrain` | Initializes persistent semantic memory brain. |
| [`sync-gbrain`](./sync-gbrain/SKILL.md) | `/sync-gbrain` | Syncs memory brain with recent repository changes. |

### 9. Mobile Engineering (iOS / SwiftUI)
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`ios-qa`](./ios-qa/SKILL.md) | `/ios-qa` | Live-device QA for SwiftUI applications. |
| [`ios-fix`](./ios-fix/SKILL.md) | `/ios-fix` | Autonomous iOS bug fixer and test repair. |
| [`ios-design-review`](./ios-design-review/SKILL.md) | `/ios-design-review` | Visual design and HIG compliance audit for iOS apps on real hardware. |
| [`ios-clean`](./ios-clean/SKILL.md) | `/ios-clean` | Cleans up debug bridge wiring from production iOS builds. |
| [`ios-sync`](./ios-sync/SKILL.md) | `/ios-sync` | Syncs iOS debug bridge with latest templates. |

### 10. Meta & Orchestration
| Skill | Command / Trigger | Purpose |
|---|---|---|
| [`gstack`](./gstack/SKILL.md) | `/gstack`, "which gstack skill fits this?" | Master router: evaluates any user request and dispatches to the optimal specialized skill. |
| [`pair-agent`](./pair-agent/SKILL.md) | `/pair-agent` | Pairs remote AI agents with local browser sessions. |
| [`benchmark`](./benchmark/SKILL.md) | `/benchmark` | Benchmarks system performance and latency. |
| [`benchmark-models`](./benchmark-models/SKILL.md) | `/benchmark-models` | Benchmarks model quality and adherence across tasks. |
| [`context-save`](./context-save/SKILL.md) | `/context-save` | Snapshots active working memory and task state. |
| [`context-restore`](./context-restore/SKILL.md) | `/context-restore` | Restores previously saved working context. |
| [`gstack-upgrade`](./gstack-upgrade/SKILL.md) | `/gstack-upgrade` | Upgrades skills suite against upstream changes. |
