# Polymarket News

Prediction markets like Polymarket aggregate collective intelligence into real-time probability estimates, but their interfaces are built for traders. This project translates those numbers into short, readable news articles using LLMs.

Built as my Bachelor's thesis at TalTech (2026).

---

## What it does

The system polls Polymarket every 30 minutes, detects significant probability movements (≥10 pp), and on user request generates two article types via an LLM:

- **Explanation** — what is this market, and what does the current probability mean?
- **Update** — what just moved, and what likely caused it?

Articles are capped at 80 words. The LLM is required to run a web search before writing and use conditional language ("likely", "may be related to") — this was the most effective lever for reducing hallucinated causal claims.

**The LLM is never called automatically.** Generation only happens on explicit user action, which keeps API costs predictable and puts a human before anything gets displayed.

---

## Stack

| | |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic, APScheduler |
| Database | PostgreSQL 16 with pgvector |
| LLM | OpenRouter (DeepSeek v3.2 by default, swappable via config) |
| Tooling | uv, ruff, mypy (strict), pytest + testcontainers + respx, ESLint, pre-commit with gitleaks |
| Infra | Docker Compose |

> **Data sources.** Polymarket is not available in Estonia, so its ingestion is **off by
> default** (`POLYMARKET_ENABLED=false`). A fresh clone uses the thesis sample markets
> (`make seed`). Kalshi and Manifold adapters are the next step; see
> [docs/MIGRATION_PLAN.md](docs/MIGRATION_PLAN.md).

---

## Structure

```
├── src/pmnews/             # Python package
│   ├── api/                # FastAPI app, routes, schemas, dependencies
│   ├── core/               # settings, UTC clock helpers
│   ├── db/                 # SQLAlchemy models, session, seed data
│   ├── ingestion/          # scheduled market fetch + upsert
│   ├── llm/                # article generation via OpenRouter
│   └── sources/            # Polymarket client
├── migrations/             # Alembic migrations
├── tests/                  # pytest suite (real Postgres in a container, HTTP mocked)
├── frontend/               # Next.js — SSR market list, CSR article generation
├── prompt-evaluation/      # Thesis evaluation harness (frozen; see below)
└── docs/                   # migration plan and design notes
```

---

## Evaluation

As part of the thesis I built a separate evaluation pipeline to compare models before picking one for production. Three writer models (DeepSeek v3.2, Gemini 3 Flash Preview, MiniMax M2.7) each generated articles for 10 real markets; DeepSeek v3.2 scored them on 5 criteria.

| Model | Score (max 50) |
|---|---|
| DeepSeek v3.2 | 32.4 |
| Gemini 3 Flash Preview | 32.3 |
| MiniMax M2.7 | 26.9 |

Grammar scores were consistently high (avg 8.5/10) across all models. Factual accuracy, verified separately via `gpt-4o-search-preview` against live sources, averaged 6.1/10 — the gap between fluency and accuracy is the main open problem for this use case.

---

## Running locally

Requires Docker, [uv](https://docs.astral.sh/uv/) and Node.js 22+.

```bash
make setup   # installs dependencies, creates .env from .env.example, installs git hooks
make up      # builds and starts db, migrations, API and frontend
make seed    # loads the thesis sample markets

# Frontend → http://localhost:3000
# API docs → http://localhost:8000/docs
```

Generating articles needs `OPENROUTER_API_KEY` in `.env`. Without it the generate
buttons return a clear 503. Article generation is disabled unless `GENERATION_MODE`
is `open` (local development, the `.env.example` default) or `token` (requires an
`X-Admin-Token` header).

| Command | What it does |
|---|---|
| `make test` | pytest against a throwaway Postgres container; no network calls |
| `make lint` / `make typecheck` | ruff, ESLint / mypy --strict, tsc --noEmit |
| `make dev` | API on the host with auto-reload (database from `make up`) |
| `make reset-db` | delete the local database volume |

The thesis evaluation harness is kept as submitted:

```bash
cd prompt-evaluation && pip install -r requirements.txt && python web_evaluate.py
```

---

**Thesis:** *Tehisintellektil põhineva uudisteplatvormi arendamine ennututurgude andmete kättesaadavuse parandamiseks* · TalTech · Supervisor: Rivo Lemmik, PhD
