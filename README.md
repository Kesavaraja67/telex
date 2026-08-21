# Telex — Self-Healing API Dependency Bot

> **Tagline:** Your dependencies just fixed themselves.

Telex watches the npm packages a repository depends on. When a tracked package ships a breaking change, Telex detects the change, finds every call site in the codebase that touches the changed API, generates a patch, and opens a single pull request with the fix explained in plain language.

## Architecture

```
telex/
├── apps/
│   ├── web/      # Next.js 15 (App Router) — marketing site + dashboard
│   └── api/      # FastAPI + asyncio workers — backend pipeline
└── .env.example  # Copy to .env and fill in credentials
```

## Quick Start

### Backend (FastAPI)
```bash
cd apps/api
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../../.env.example ../../.env   # fill in values
alembic upgrade head
uvicorn main:app --reload --port 8000
# In another terminal:
python -m jobs.worker
```

### Frontend (Next.js)
```bash
cd apps/web
npm install
cp ../../.env.example .env.local   # fill in NEXTAUTH_* and NEXT_PUBLIC_API_URL
npm run dev
```

## Build Order

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold, DB, landing page, backend skeleton | ✅ |
| 1 | Manual pipeline: hardcode one change, get a Gemini patch | 🔜 |
| 2 | Automate tree-sitter scanning | 🔜 |
| 3 | GitHub App install + auto-PR | 🔜 |
| 4 | Real landing page interactions | ✅ |
| 5 | Dashboard auth + patch review | ✅ |
| 6 | Changelog parsing, real repos | 🔜 |
| 7 | LoRA fine-tune (optional) | 🔜 |

## Environment Variables

See [`.env.example`](.env.example) for all required variables.

## Guardrails

- **Never auto-merge.** Every PR waits for human review.
- **Verify webhook signatures** on every `/webhooks/github` request.
- **Rate-limit LLM calls** per repo per day.
- **Idempotent job handlers** — enforced via UNIQUE constraints.
- **Log every patch and PR** with provider + model for auditability.
