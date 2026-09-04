# Telex System Architecture & Technical Specification

> **Autonomous AI Revenue Recovery & Self-Healing Patch Agent for Live Razorpay Payment Failures**  
> *Engineered for the Razorpay Pay 2026 Buildathon.*

---

## 1. Executive System Topology

Telex operates across two synchronized engines sharing a single unified job queue, verification gate, and database substrate:

```text
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   INGESTION LAYER                                      │
 └────────────────────────────────────────────────────────────────────────────────────────┘
          │                                                               │
 [ Trigger 1: Upstream Registry ]                         [ Trigger 2: Live Razorpay Telemetry ]
   - npm release webhooks / polling                         - Razorpay Checkout errors
   - Public API signature changes                           - Webhook signature mismatches
   - Breaking interface diffs                               - Order total currency mismatches
          │                                                               │
          ▼                                                               ▼
 ┌───────────────────────────────────┐               ┌───────────────────────────────────┐
 │             ENGINE A              │               │             ENGINE B              │
 │  (Tree-Sitter AST Code Scanner)   │               │   (Two-Tier Recovery Classifier)  │
 └───────────────────────────────────┘               └───────────────────────────────────┘
          │                                                    /                 \
          │                                           [ Transient ]         [ Code Defect ]
          │                                                │                       │
          │                                                ▼                       │
          │                                      ┌──────────────────┐              │
          │                                      │  recover_runtime │              │
          │                                      │ (Bounded Backoff)│              │
          │                                      └──────────────────┘              │
          │                                                │                       │
          │                                         [ ₹ Recovered ]                │
          │                                                                        │
          └───────────────────────────────┬────────────────────────────────────────┘
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │            generate_patch             │
                      │   (Gemini 2.5 Flash / Claude AST)     │
                      └───────────────────────────────────────┘
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │    EPHEMERAL GITHUB ACTIONS GATE      │
                      │  (Isolated Branch + Real Native CI)   │
                      │   npm ci → npx tsc → npm test         │
                      └───────────────────────────────────────┘
                                          │
                                  [ 100% Verified ]
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │                open_pr                │
                      │      (Human-Reviewed GitHub PR)       │
                      └───────────────────────────────────────┘
```

---

## 2. Two-Tier Classification State Machine (Engine B)

A critical engineering failure in naive AI agent architectures is passing raw payment timeouts or standard gateway error codes directly to costly, non-deterministic LLMs. Telex solves this with a **zero-token, sub-millisecond fast-path**:

### Tier-1 Deterministic Fast-Path Table (`<1ms`, 0 Tokens, 0 Hallucinations)

| Failure Type | Root Cause | Classification | Automated Remediation | LLM Invocation |
|---|---|---|---|---|
| `timeout` | Gateway network delay / TCP drop | `transient` | Bounded exponential retry | **None (0 tokens)** |
| `rate_limit` | Razorpay 429 throttling | `transient` | Jittered backoff retry | **None (0 tokens)** |
| `db_unavailable` | Merchant DB lock / transient 500 | `transient` | Bounded retry backoff | **None (0 tokens)** |
| `card_declined` | Customer card issuer rejection | `transient` | Hard stop after 2 declines (anti-fraud) | **None (0 tokens)** |
| `order_total_mismatch` | Frontend vs backend paise bug | `code_defect` | Escalate to Engine A AST Patching | **None (0 tokens)** |
| `webhook_signature_mismatch` | HMAC secret / payload bug | `code_defect` | Escalate to Engine A AST Patching | **None (0 tokens)** |

### Tier-2 Semantic LLM Fallback (Ambiguous/Unrecognized Errors Only)
If a gateway error is novel, unstructured, or ambiguous, it is routed to **Gemini 2.5 Flash** with strict JSON output schemas:
```json
{
  "classification": "transient" | "code_defect" | "unknown",
  "reasoning": "Detailed technical analysis of the failure payload",
  "confidence": 0.95
}
```

---

## 3. Ephemeral GitHub Actions Verification Gate (Engine A)

Telex never assumes that an LLM-generated patch is bug-free. Instead of relying on simulated diff parsers or local system clones that diverge from the target repository, Telex uses an **ephemeral native CI gate**:

1. **Candidate Branch Creation**: Telex creates a dedicated verification branch:  
   `telex/verify-<event-id>`
2. **Atomic Verification Bundle**: Using PyGithub's Git Data API, Telex commits:
   - The candidate unified patch applied to the target code.
   - An auto-generated ephemeral GitHub Actions workflow: `.github/workflows/telex-verification.yml`.
3. **Native Runner Execution**: GitHub Actions executes the target repository's **real package dependencies, TypeScript compilation (`npx tsc --noEmit`), and full test runner (`npm test`)** on clean Ubuntu runners.
4. **Autonomous Status Polling**: Telex monitors the check runs via the GitHub API with bounded exponential backoff.
5. **Gating Rule**:
   - **PASS (100% Green)** → Clean pull request opened with detailed verification receipts.
   - **FAIL** → Bounded retry with compiler feedback, or immediate rejection. **Zero hallucinated code ever reaches a production pull request.**

---

## 4. Honest Metric Methodology (P0-2)

Telex enforces a strict, mathematically sound separation between money actually recovered and automated ticket management:

$$\text{Payment Recovery Rate} = \frac{\text{Transactions Recovered (₹)}}{\text{Total Failed Transactions}}$$

$$\text{Recovery Execution Rate} = \frac{\text{Recovered} + \text{Escalated}}{\text{Total Failed Transactions}}$$

$$\text{Revenue at Risk} = \sum (\text{Unresolved Failed Transactions in Paise})$$

- **Payment Recovery Rate** only counts transactions where money was successfully collected into the merchant's Razorpay account.
- **Recovery Execution Rate** reflects all failures handled safely (resolved or escalated with PRs) without silent loss.

---

## 5. Security Model & Deliberate Stop Safety Guardrails

- **Cryptographic Webhook Validation**: All inbound webhooks are cryptographically authenticated via HMAC-SHA256:
  - Razorpay: `X-Razorpay-Signature` against `RAZORPAY_WEBHOOK_SECRET`
  - GitHub: `X-Hub-Signature-256` against `GITHUB_WEBHOOK_SECRET`
- **Deliberate Stopping Rules**: Hard stops after 2 card declines on the same order to protect merchants from card testing attacks and fraud score penalties.
- **Zero Auto-Merge**: Every code defect resolution generates a clean, isolated branch and human-reviewed pull request.
- **Production Secret Guard**: In `ENVIRONMENT=production`, the API process fails loudly at boot if required credentials (`RAZORPAY_TEST_KEY_ID`, `RAZORPAY_TEST_KEY_SECRET`, `GEMINI_API_KEY`) are missing.
