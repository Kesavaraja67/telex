# Telex — Demo & Reproduction Guide (15-Minute Evaluator Walkthrough)

This guide walks through reproducing the two flagship scenarios of Telex end-to-end:
1. **Scenario 1: Live Payment Failure → Deterministic Tier-1 Classification → Auto-Recovery (₹500 Recovered)**
2. **Scenario 2: Code Defect (Order Total Mismatch) → Escalation → LLM Patch Synthesis → Human-Reviewed GitHub PR**

---

## 🚀 Live Demo URLs
- **Telex Dashboard**: [https://telex-pi.vercel.app](https://telex-pi.vercel.app)
- **Recovery Stream**: [https://telex-pi.vercel.app/dashboard/recovery](https://telex-pi.vercel.app/dashboard/recovery)
- **Backend API**: [https://telex-api.onrender.com](https://telex-api.onrender.com)
- **API Health**: [https://telex-api.onrender.com/health](https://telex-api.onrender.com/health)

---

## Scenario 1: Transient Timeout Recovery Flow

### Step 1: Open the Recovery Stream
Open [https://telex-pi.vercel.app/dashboard/recovery](https://telex-pi.vercel.app/dashboard/recovery) in your browser. Notice the **Live Telemetry Stream** counter.

### Step 2: Inject a Transient Failure (or Run a Batch)
Using curl or the UI Batch Simulator:
```bash
curl -X POST "https://telex-api.onrender.com/api/payments/batch-run" \
  -H "Content-Type: application/json" \
  -H "x-demo-key: ${DEMO_KEY:-your_demo_key}" \
  -d '{"count": 10, "failure_rate": 0.5}'
```

### Step 3: Observe Real-Time Pipeline Processing
1. **Detection**: `PaymentAttempt` records the failure (`timeout` or `network_error`).
2. **Tier-1 Deterministic Classification**:
   - `diagnose_runtime_failure` maps `timeout` → `transient` with `0 tokens`, `0 latency`, and `llm_provider="none"`.
3. **Auto-Retry Backoff**:
   - `recover_runtime` worker retries the transaction.
4. **Resolution**:
   - Status updates to `recovered`.
   - Hero metric **Revenue Recovered** increments by the exact transaction amount in paise.

---

## Scenario 2: Code Defect Escalation to Verified GitHub PR

### Step 1: Report a Client-Side Order Total Mismatch
When a client detects that an order summary calculated on the frontend does not match the buggy backend calculation:
```bash
# 1. Create an attempt
ATTEMPT_RESP=$(curl -s -X POST "https://telex-api.onrender.com/api/payments/create-order" \
  -H "Content-Type: application/json" \
  -d '{"amount": 99900}')

ATTEMPT_ID=$(echo $ATTEMPT_RESP | grep -o '"payment_attempt_id":"[^"]*' | cut -d'"' -f4)

# 2. Report order total mismatch (e.g. expected ₹999 vs calculated ₹950)
curl -X POST "https://telex-api.onrender.com/api/payments/report-mismatch" \
  -H "Content-Type: application/json" \
  -d "{
    \"payment_attempt_id\": \"$ATTEMPT_ID\",
    \"expected_total_paise\": 99900,
    \"actual_total_paise\": 95000
  }"
```

### Step 2: Observe the Escalation
1. `RecoveryEvent` is immediately created with `classification="code_defect"`.
2. Engine B identifies the suspect source location via `FAILURE_LOCATION_MAP`.
3. A `DetectedChange` and `CodeUsage` are seeded in the database.
4. `generate_patch` is enqueued (shared with Engine A).
5. The LLM provider (Gemini 2.5 Flash / Claude) synthesizes a unified git diff.
6. The verification gate runs typechecks and structural validations.
7. A human-reviewed Pull Request is opened on GitHub without touching production code directly.

---

## Running Local Verification Tests

Telex includes 37 automated tests across unit and E2E integration suites:

```bash
cd apps/api
pip install -r requirements.txt
pytest -v --tb=short
```

To run the E2E recovery flow specifically:
```bash
pytest tests/test_e2e_recovery_flow.py -v
```
