<p align="center">
  <img src="apps/web/public/logo.svg" width="96" height="96" alt="Telex Logo" />
</p>

<h1 align="center">Telex</h1>

<p align="center">
  <strong>Autonomous AI Revenue Recovery & Self-Healing Patch Agent for Live Razorpay Payment Failures.</strong><br>
  <em>Built for the Razorpay Pay 2026 Buildathon.</em><br>
  <em>Detect revenue at risk → Classify deterministically (Tier 1) or via LLM (Tier 2) → Execute bounded recovery → Escalate code defects to verified GitHub PRs.</em>
</p>

<p align="center">
  <a href="https://telex-pi.vercel.app"><img src="https://img.shields.io/badge/Live_Dashboard-telex--pi.vercel.app-white?style=flat-square&logo=vercel" alt="Live Dashboard" /></a>
  <a href="https://telex-pi.vercel.app/dashboard/recovery"><img src="https://img.shields.io/badge/Live_Telemetry-Recovery_Stream-black?style=flat-square" alt="Live Stream" /></a>
  <a href="https://telex-api.onrender.com/health"><img src="https://img.shields.io/badge/API_Status-Live_200_OK-green?style=flat-square" alt="API Status" /></a>
  <a href="ARCHITECTURE.md"><img src="https://img.shields.io/badge/Architecture-ARCHITECTURE.md-purple?style=flat-square" alt="Architecture" /></a>
  <a href="DEMO.md"><img src="https://img.shields.io/badge/Reproduction_Guide-DEMO.md-blue?style=flat-square" alt="Demo Guide" /></a>
  <img src="https://img.shields.io/badge/Tests-40%2F40_Passing-brightgreen?style=flat-square" alt="Tests 40 Passing" />
</p>

---

## Overview

Telex is an autonomous revenue recovery and software healing system designed to eliminate merchant revenue loss caused by transient infrastructure outages and upstream code defects.

1. **Engine B (Live Revenue Recovery & Detection)**: Intercepts failed transactions in Razorpay Test Mode, classifies them through an intelligent **two-tier classifier** (deterministic rule lookup vs. LLM judgment), executes bounded retries with exponential backoff for transient issues, and records verified revenue recovered.
2. **Engine A (Unified Code Defect Repair & PR Substrate)**: When a code defect is diagnosed (e.g. `order_total_mismatch`, `webhook_signature_mismatch`), Telex seeds a suspect call-site representation via Tree-Sitter AST, prompts an LLM (Gemini 2.5 Flash / Claude) for a unified git patch, verifies it in an isolated clone sandbox (test & typecheck gates), and opens a **human-reviewed GitHub Pull Request**.

```text
                     ┌────────────────────────────────────────────────────────┐
                     │                      TELEX ENGINE                      │
                     └────────────────────────────────────────────────────────┘
                                 │                                 │
                   [ Trigger 1: npm Breakage ]       [ Trigger 2: Payment Failure ]
                                 │                                 │
                        extract_changes                  detect_payment_failure
                                 │                                 │
                            scan_repo                 diagnose_runtime_failure
                         (Tree-Sitter AST)             (Two-Tier Classification)
                                 │                            /         \
                                 │              [ Transient ]             [ Code Defect ]
                                 │                   │                          │
                                 │             recover_runtime                  │
                                 │           (Auto-Retry Backoff)               │
                                 │                   │                          │
                                 │              [ Resolved ]                    │
                                 │             (₹ Recovered)                    │
                                 │                                              │
                                 └──────────────────────┬───────────────────────┘
                                                        │
                                                 generate_patch
                                             (LLM: Gemini / Claude)
                                                        │
                                                 verify_in_clone
                                             (Typecheck & Test Gates)
                                                        │
                                                     open_pr
                                           (Human-Reviewed GitHub PR)
```

---

## Key Engineering Innovations

### 1. Honest Metric Methodology (P0-2)
Unlike naive bots that count escalating an issue as "recovering" it, Telex separates metrics explicitly:
- **Payment Recovery Rate**: `recovered / total_failures` (only real money collected).
- **Recovery Execution Rate**: `(recovered + escalated) / total_failures` (all handled failures).
- **Revenue at Risk**: Unrecovered failed payment value.

### 2. Two-Tier Classifier: Zero-Token Deterministic Fast-Path
Telex does not blindly pass plain timeouts to an LLM. 
- **Tier 1 (Deterministic Table)**: Known signatures (`timeout`, `rate_limit`, `db_unavailable`, `card_declined`, `webhook_signature_mismatch`, `order_total_mismatch`) resolve instantly with **0 tokens, 0 latency, and 0 hallucination risk**.
- **Tier 2 (LLM Fallback)**: Reserved exclusively for unrecognized or ambiguous gateway errors.

### 3. Safety Guardrails & Bounded Recovery
- **Deliberate Stop Rules**: Hard stops after 2 card declines on the same order to prevent card spam and fraud flags.
- **Never Auto-Merge**: Every code patch is sandboxed, verified through test gates, and submitted as a human-reviewed PR.
- **HMAC Webhook Verification**: Cryptographic validation on all GitHub (`X-Hub-Signature-256`) and Razorpay (`X-Razorpay-Signature`) webhooks.
- **Production Secret Enforcement**: Server fails loudly at startup in `ENVIRONMENT=production` if real API secrets are absent.

---

## Feature Matrix

| Component | Feature | Implementation Details | Status |
|---|---|---|---|
| **Engine B** | Razorpay Test Mode | Real Checkout order creation, webhook verification & status tracking | Live |
| **Engine B** | Incident Bridge | `POST /api/payments/report-mismatch` client detection bridge | Live |
| **Engine B** | Two-Tier Classifier | Tier-1 deterministic lookup + Tier-2 LLM fallback | Live |
| **Engine B** | Bounded Auto-Recovery | Non-blocking retry worker with deliberate stopping rules | Live |
| **Engine A** | Tree-Sitter AST Scanner | Multi-language AST call site scanning (`.ts`, `.tsx`, `.js`) | Live |
| **Engine A** | Patch Generator | Gemini 2.5 Flash / Claude unified diff synthesis | Live |
| **Engine A** | Verification Gate | Ephemeral GitHub Actions CI gate (real target repo build + test suite) & clone sandbox | Live |
| **Engine A** | GitHub App Integration | Automated branch creation & human-reviewed PR submission | Live |
| **Job Queue** | Async DB Job Worker | PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` + heartbeats | Live |
| **Dashboard** | Next.js 16 Web App | Real-time telemetry, recovery tickets, and live event stream | Live |
| **CI & Testing**| GitHub Actions CI | Automated backend pytest + frontend tsc lint pipeline | Live |

---

## Quick Start & Local Setup

### 1. Clone & Configure Environment
```bash
git clone https://github.com/Kesavaraja67/telex.git
cd telex
cp .env.example .env
```

### 2. Backend (FastAPI + Async Worker)
```bash
cd apps/api
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head

# Run API Server
uvicorn main:app --reload --port 8000
```

### 3. Frontend (Next.js Dashboard)
```bash
cd apps/web
npm install
npm run dev
```
Open [http://localhost:3000/dashboard/recovery](http://localhost:3000/dashboard/recovery) to view the live payment recovery portal.

---

## Automated Test Suite (40 Tests)

The test suite validates both Engine A and Engine B end-to-end against an in-process SQLite database without external dependencies:

```bash
cd apps/api
pytest -v --tb=short
```

### Test Coverage Breakdown (40/40 Passing):
- **`test_e2e_recovery_flow.py` (7 E2E Tests)**:
  - `test_transient_failure_full_recovery_cycle`: Real timeout → Tier 1 classify → auto-retry → recovered → ₹ recorded.
  - `test_code_defect_full_pr_cycle`: Mismatch report → code_defect → seed `DetectedChange`/`CodeUsage` → `generate_patch` enqueued.
  - `test_report_mismatch_validation`: 400 on identical amounts, 404 on missing attempt, 400 on mismatched amount.
  - `test_derive_stage_all_combinations`: Verifies all 7 outcome × classification stage derivations.
  - `test_payment_recovery_rate_vs_execution_rate`: Asserts distinction between recovered and execution metrics.
  - `test_bounded_stopping_repeated_card_declines`: Asserts deliberate stop at 3 attempts for unrecoverable declines.
  - `test_duplicate_webhook_delivery_idempotent_ignored`: Asserts cryptographic webhook idempotency on duplicate event IDs.
- **`test_diagnose_runtime_failure.py` (7 Tests)**: Deterministic classification lookup, markdown fence parsing, JSON extraction, Tier 2 LLM routing.
- **`test_payment_service.py` (10 Tests)**: HMAC signature validation, simulated payment errors, Razorpay decline card rules.
- **`test_patch_generation.py` (11 Tests)**: Unified diff extraction, scope validation, clone verification sandbox, required-tests policies, and ephemeral GitHub Actions CI verification gate (`test_verify_patch_via_github_actions_success`).
- **`test_code_scanner.py` (5 Tests)**: Tree-Sitter AST call-site discovery across JS/TS/TSX.

For step-by-step evaluation instructions, see [DEMO.md](DEMO.md).
