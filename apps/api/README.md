# Telex API — Backend Service & Autonomous Recovery Worker

> **FastAPI REST API, PostgreSQL Job Queue, and Autonomous Code Repair Substrate**  
> *Engineered for the Razorpay Pay 2026 Buildathon.*

---

## Overview

The `apps/api` service powers Telex's payment failure detection, two-tier classification, bounded auto-recovery, and self-healing pull request generation.

It runs as an asynchronous FastAPI application paired with a PostgreSQL row-level locked job queue (`SELECT ... FOR UPDATE SKIP LOCKED`), ensuring zero-duplicate execution across distributed workers.

---

## Key Modules & Responsibilities

| Path | Responsibility |
|---|---|
| `routers/payments.py` | Order creation, payment attempt tracking, batch failure simulator, and mismatch incident reporting. |
| `routers/webhooks.py` | Cryptographic HMAC validation for Razorpay (`X-Razorpay-Signature`) and GitHub (`X-Hub-Signature-256`). |
| `services/payment_service.py` | Razorpay Test Mode client wrapper, HMAC verification, and test card decline rules. |
| `services/github_service.py` | GitHub App authentication, atomic Git Data tree commits, ephemeral CI workflow synthesis, and check run polling. |
| `services/code_scanner.py` | Tree-Sitter AST parser for JavaScript, TypeScript, and TSX call-site discovery. |
| `services/patch_providers/` | Gemini 2.5 Flash and Claude unified diff synthesis providers with exponential retry backoff. |
| `jobs/handlers/` | Asynchronous worker tasks: `detect_payment_failure`, `diagnose_runtime_failure`, `recover_runtime`, `generate_patch`, `open_pr`. |

---

## Endpoint Catalog

### Payment & Recovery API (`/api/payments`)
- `POST /api/payments/create-order`: Creates a Razorpay Test Mode order and records a `PaymentAttempt`.
- `POST /api/payments/pay/{id}`: Simulates customer checkout with optional failure injection (`x-demo-key` protected).
- `POST /api/payments/batch-run`: Injects a configurable batch of payments and simulated failure rates for live testing.
- `POST /api/payments/report-mismatch`: Client incident bridge for reporting order total discrepancies (e.g., expected ₹999 vs actual ₹950).
- `GET /api/payments/stats`: Computes Payment Recovery Rate, Execution Rate, and Revenue at Risk in real time.
- `GET /api/payments/events`: Returns the live telemetry stream of `RecoveryEvent` records for dashboard visualization.

### System Health (`/health`)
- `GET /health`: Returns JSON status `{"status": "ok", "environment": "production"}`.

---

## Local Setup & Development

### 1. Virtual Environment & Dependencies
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Database Migrations
```bash
alembic upgrade head
```

### 3. Start the API & Embedded Worker
```bash
uvicorn main:app --reload --port 8000
```

---

## Automated Test Suite (40/40 Passing)

Run the full test suite with verbose output:
```bash
pytest -v --tb=short
```

Expected result:
```text
======================= 40 passed, 8 warnings in 3.40s =======================
```

To run individual suites:
- **E2E Recovery Suite**: `pytest tests/test_e2e_recovery_flow.py -v`
- **Payment & HMAC Suite**: `pytest tests/test_payment_service.py -v`
- **Patch Generation & CI Gate**: `pytest tests/test_patch_generation.py -v`
- **Two-Tier Classifier**: `pytest tests/test_diagnose_runtime_failure.py -v`
- **Tree-Sitter AST Scanner**: `pytest tests/test_code_scanner.py -v`
