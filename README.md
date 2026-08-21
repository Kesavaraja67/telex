# Telex — Self-Healing Code & Payment Platform

> **Autonomous self-healing for breaking API dependencies and live payment failures.**
> One engine. Two triggers. One human-reviewed output path.

---

## 🌟 Overview

Telex is an autonomous healing system designed to eliminate production downtime caused by breaking upstream changes and transient infrastructure failures. It operates as a single unified engine driven by two independent sensors:

1. **Engine A (Dependency Healing)**: Detects breaking API changes in watched npm packages, performs AST-level repository call site scanning using tree-sitter, generates minimal unified diff patches using LLMs (Gemini / Claude), and opens structured GitHub Pull Requests.
2. **Engine B (Runtime Payment Recovery)**: Detects live payment transaction failures in Razorpay Test Mode, classifies them through an intelligent **two-tier classifier** (deterministic rule lookup vs. LLM judgment), executes automated retries with backoff for transient issues, and escalates code defects into the exact same Engine A PR pipeline.

```
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
                                 │                                              │
                                 └──────────────────────┬───────────────────────┘
                                                        │
                                                 generate_patch
                                             (LLM: Gemini / Claude)
                                                        │
                                                     open_pr
                                           (Human-Reviewed GitHub PR)
```

---

## 🏗️ Architecture & Philosophy

### 1. One Engine, Two Sensors, One Output Path
Runtime code defects in payment handlers do not modify production files directly without human oversight. Instead, when a `code_defect` is diagnosed, Engine B seeds an internal `DetectedChange` and `CodeUsage` representation of the suspect handler and enters the **same `generate_patch` → `open_pr` pipeline** used by Engine A. Every code change requires human review.

### 2. AI Judgment: Two-Tier Classification
Telex avoids using LLMs blindly for every simple failure. An LLM should not be asked to classify a plain network timeout — doing so adds latency, cost, and hallucination risk without added value.

- **Tier 1 — Deterministic Rule Table (0 tokens, instant, 0 hallucination risk)**: Known failure signatures (`timeout`, `rate_limit`, `db_unavailable`, `network_error`, `webhook_signature_mismatch`) are classified instantly via a rule dictionary with `llm_provider="none"`.
- **Tier 2 — LLM Fallback (Ambiguous Cases Only)**: Unrecognized or unstructured error signatures are routed to Gemini / Claude with prompts emphasizing that the failure was unresolvable by the rule table.

### 3. Transparent Failure Injection & Real Razorpay Integration
Built on real-world production Razorpay integration patterns:
- **`card_declined`**: Real Razorpay Test Mode API calls executed using documented Visa decline test card numbers (`4100280000060003`).
- **`timeout` & `db_unavailable`**: Injected locally at the service boundary because Razorpay provides no API lever for external network timeouts or database outages.
- **Webhook HMAC Verification**: Strict SHA-256 HMAC signature validation matching production webhook handling.

---

## 📊 Current Build & Feature Status

| Component | Feature | Implementation Details | Status |
|---|---|---|---|
| **Engine A** | Package Version Polling | Detects new npm releases & extracts API changelog diffs | ✅ Live |
| **Engine A** | Tree-Sitter AST Scanner | Multi-language AST call site scanning (`.ts`, `.tsx`, `.js`) | ✅ Live |
| **Engine A** | Patch Generation | Multi-provider unified diff generation (Google Gemini 2.0 / Claude) | ✅ Live |
| **Engine A** | GitHub App Integration | Automated branch creation, patch validation & PR opening | ✅ Live |
| **Engine B** | Razorpay Test Mode Client | Order creation, payment simulation, and webhook signature verification | ✅ Live |
| **Engine B** | Failure Detection | Ingestion of payment failures & atomic recovery event creation | ✅ Live |
| **Engine B** | Two-Tier Classifier | Tier 1 deterministic table + Tier 2 LLM fallback | ✅ Live |
| **Engine B** | Auto-Recovery & Escalation | Non-blocking retry in worker threads + escalation to Engine A PR pipeline | ✅ Live |
| **Job Queue** | Async DB Job Worker | PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` with heartbeats and reaper | ✅ Live |
| **Dashboard** | Next.js 15 Web App | Real-time overview, watched repos, live batch simulator & recovery tickets | ✅ Live |
| **Test Suite** | Automated Tests | Comprehensive pytest suite covering payment service & classification | ✅ Live |

---

## 🛡️ Guardrails & Safety

- **Never Auto-Merge**: All code patches require human review and approval on GitHub.
- **HMAC Webhook Verification**: Cryptographic validation on all GitHub (`X-Hub-Signature-256`) and Razorpay (`X-Razorpay-Signature`) webhooks.
- **Worker Concurrency & Heartbeats**: Background workers run heartbeats during long handler tasks and employ a stale-job reaper to prevent zombie jobs.
- **Auditable History**: Every classification and patch records the provider, model, prompt version, and timestamp.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL

### 1. Clone & Configure Environment
```bash
git clone https://github.com/Kesavaraja67/telex.git
cd telex
cp .env.example .env
```
Fill in the required keys in `.env` (Database URL, Gemini API Key, GitHub App credentials, and Razorpay Test Mode keys).

### 2. Backend (FastAPI + Worker)
```bash
cd apps/api
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head

# Terminal 1: API Server
uvicorn main:app --reload --port 8000

# Terminal 2: Background Worker
python -m jobs.worker
```

### 3. Frontend (Next.js Dashboard)
```bash
cd apps/web
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to view the dashboard and [http://localhost:3000/dashboard/recovery](http://localhost:3000/dashboard/recovery) for the Payment Recovery portal.

---

## 🧪 Running Automated Tests

A dedicated test suite validates the core payment service logic, webhook security, and two-tier classification engine:

```bash
cd apps/api
pytest -v
```

### Test Suite Highlights:
- `test_verify_webhook_signature_*`: Validates HMAC-SHA256 signature verification, timing attack safety, and rejection of tampered/missing payloads.
- `test_simulate_payment_*`: Tests separation of locally-injected infrastructure failures vs. real Razorpay Test Mode decline responses.
- `test_tier1_deterministic_classifications`: Validates zero-token deterministic short-circuiting for standard errors.
- `test_diagnose_handler_tier2_llm_flow`: Tests LLM fallback and metadata capture for ambiguous runtime failures.
