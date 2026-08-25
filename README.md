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
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4 |
| Backend | FastAPI, APScheduler, SQLAlchemy |
| Database | PostgreSQL 16 |
| LLM | OpenRouter (DeepSeek v3.2 by default, swappable via config) |
| Infra | Docker Compose |

---

## Structure

```
├── frontend/               # Next.js — SSR market list, CSR article generation
├── backend/                # FastAPI — ingestion, LLM calls, REST API
│   └── app/
│       ├── api/            # /markets, /explain, /generate-updates
│       ├── db/             # markets · market_snapshots · articles
│       └── services/       # Polymarket client, LLM service, scheduler
└── prompt-evaluation/      # Standalone eval module (no backend dependency)
    ├── web_writer.py       # Generates articles with mandatory web search
    ├── evaluator.py        # LLM-as-a-judge scorer, 5 criteria, max 50 pts
    └── grounded_eval.py    # Fact-checks claims against live web via gpt-4o
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

```bash
cp .env.example .env
docker compose up --build

# Frontend  → http://localhost:3000
# Backend   → http://localhost:8000/docs
```

Without Docker:

```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# Evaluation
cd prompt-evaluation && pip install -r requirements.txt
python web_evaluate.py
```

---

**Thesis:** *Tehisintellektil põhineva uudisteplatvormi arendamine ennututurgude andmete kättesaadavuse parandamiseks* · TalTech · Supervisor: Rivo Lemmik, PhD
