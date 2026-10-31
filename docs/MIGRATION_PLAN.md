# Migration plan: thesis prototype → production portfolio project

Status: **approved 2026-10-31**, including the deviations in §3 (package layout,
Airflow in Phase 3, single EC2 host). The thesis is tagged `v1-thesis`; work happens on `production`.

This document records what the repository looks like today, what will be kept or
replaced, the main risks, and the phase order. Facts marked *(probed 2026-10-31)*
were checked live from the development machine in Estonia.

---

## 1. Current state

### 1.1 Repository layout

```
.
├── backend/                 FastAPI app (Python 3.12 in Docker)
│   ├── app/main.py          app factory + APScheduler job + Polymarket upsert logic
│   ├── app/api/routes/      markets.py (list/get/explain/generate-updates), articles.py
│   ├── app/services/        polymarket.py (Gamma + CLOB client), llm.py (OpenRouter)
│   ├── app/db/              SQLAlchemy async models: markets, market_snapshots, articles
│   ├── app/schemas/         Pydantic response models
│   └── alembic/             configured, but versions/*.py is gitignored → no migrations
├── frontend/                Next.js 15.2.0 App Router, React 19, Tailwind 4
│   └── src/components/      MarketCard.tsx (528 lines, inline styles), MarketList, ThemeToggle
├── prompt-evaluation/       thesis LLM-as-judge harness (standalone scripts)
│   ├── web_writer.py        3 writer models via OpenRouter web_search tool
│   ├── evaluator.py         judge rubric: 5 criteria × 0–10
│   ├── grounded_eval.py     re-scores factual_consistency against fetched reference docs
│   ├── sample_data.py       10 hand-picked April 2026 Polymarket cases (5 explanation, 5 update)
│   └── results/             JSON/CSV/MD/.numbers outputs, plot script, figure
├── docker-compose.yml       postgres:16, backend (--reload, bind mount), frontend
└── .env.example             (out of date, see 1.4)
```

### 1.2 Runtime data flow

```
APScheduler (inside the API process, every 30 min)
  → Polymarket Gamma /markets?tag_id=… (top 10 by volume × 4 tags)
  → upsert markets, insert one market_snapshots row per market per day
User clicks "Explain" / "Generate updates" in the UI
  → FastAPI calls OpenRouter (DeepSeek v3.2 + web-search plugin)
  → parses "TITLE:/BODY:" text → stores in articles
"Generate updates" also back-fills daily prices from the Polymarket CLOB API
  and writes one LLM article per day with a >10 pp move.
```

### 1.3 Thesis evaluation

- 10 cases × 3 writer models (DeepSeek v3.2, Gemini 3 Flash preview, MiniMax M2.7) = 30 articles.
- Judge: DeepSeek v3.2 with web search. Model averages in `results/web_eval_*.md`:
  Gemini 28.6/50, DeepSeek 28.0/50, MiniMax 23.7/50.
- `grounded_eval.py` re-scored factual consistency for 24 of 30 articles against
  fetched source documents, with `openai/gpt-4o-search-preview` as the judge: overall
  average 2.29 → 7.0 out of 10 on those 24.
- The CSV in the working tree has been patched (`results/patch_factual.py`, untracked)
  to replace factual scores with the grounded ones for those 24 rows. The `.md` file
  still shows the original scores. **Decision:** the thesis reports the grounded factual
  scores, so the README quotes the patched CSV and states the method.

### 1.4 Problems found while reading the code

Correctness and safety:

| # | Where | Problem |
|---|-------|---------|
| 1 | `routes/markets.py` explain + generate-updates | No auth or rate limit. Anyone who can reach the public URL can trigger paid LLM calls. **Must be fixed before any deployment.** |
| 2 | `generate-updates` | Fetches the full price history (`interval=max`) and makes one LLM call per >10 pp day with no upper bound: one click can trigger dozens of paid calls. |
| 3 | `explain` | Docstring says it returns 409 if an article exists; it now regenerates and overwrites on every click (one paid call per click). |
| 4 | `main.py` lifespan | Startup waits for a full fetch. From Estonia, Polymarket times out, so startup blocks for about 4 × 30 s before serving. |
| 5 | `main.py` `_upsert_markets` | A failed price parse silently stores probability `0.0`. |
| 6 | `polymarket.py` | `strftime("%s")` is a non-portable glibc extension and uses local time; `date.fromtimestamp` also uses local time. |
| 7 | models / main | `datetime.utcnow()` (deprecated in 3.12) and naive datetimes throughout. |
| 8 | `generate-updates` | `inserted` reports attempted rows, not inserted rows. |
| 9 | `GET /markets` | Returns every market with all articles and all snapshots, no pagination. The payload grows every day. |
| 10 | `models.py` | `articles.market_id` has no index; `selectinload(Market.articles)` scans the table. Natural candidate for the Phase 3 SQL write-up. |
| 11 | frontend | Next.js 15.2.0 is affected by published security advisories, including the December 2025 React Server Components RCE advisory, which affects App Router apps. Upgrade to a patched release and confirm with `npm audit`. |

Hygiene:

- Config drift: README and `.env.example` mention `ANTHROPIC_API_KEY` / `claude-sonnet-4-6`,
  the code reads `OPENROUTER_API_KEY` / `deepseek/deepseek-v3.2`. Frontend reads
  `NEXT_PUBLIC_BACKEND_URL`, `.env.example` defines `NEXT_PUBLIC_API_URL`.
  `backend/.env.example` duplicates the root one.
- No tests, no linters or type-checker config, no CI, no lockfiles (`package-lock.json`
  missing, Python deps unpinned transitively).
- Alembic is set up but migrations are gitignored; the app uses `create_all` on startup.
- The scheduler runs inside the API process, so N workers means N schedulers.
- The browser calls FastAPI directly (to avoid the Next.js proxy timing out on slow
  LLM calls), so the API must be public and CORS-enabled.
- `ESLint 9` with no `eslint.config.*` means `npm run lint` does not run as-is.
- Backend Docker image runs `uvicorn --reload` with the source bind-mounted (dev-only setup).
- Local `python3` is 3.9 and `backend/.venv` is 3.9; the code needs ≥3.10 (`X | None` at runtime).

Good news:

- No secrets in git history or in tracked files (scanned all commits for OpenRouter,
  Anthropic, OpenAI and AWS key patterns). `.env` is gitignored and never committed.

### 1.5 Data sources from Estonia *(probed 2026-10-31, IP geolocated to EE)*

| Source | Endpoint | Result |
|--------|----------|--------|
| Kalshi | `api.elections.kalshi.com/trade-api/v2/markets`, `/events`, `/series/{s}/markets/{t}/candlesticks` | **200**, no auth, about 0.2 s |
| Manifold | `api.manifold.markets/v0/markets` | **200**, no auth |
| Polymarket | `gamma-api.polymarket.com`, `clob.polymarket.com` | **Connection timeout** (blocked at network level) |

Kalshi details that shape the adapter:

- The default `/markets` listing is dominated by zero-volume multi-leg combo markets
  (`KXMVE…` tickers with `mve_collection_ticker`). Ingest through
  `/events?with_nested_markets=true` and exclude combo markets.
- Prices are fixed-point dollar strings (`last_price_dollars: "0.9900"`), volumes are
  `*_fp` strings. Parse as `Decimal`, never `float`, at the boundary.
- Daily candles for a market with no trades in a period have no traded price, only
  `yes_bid` / `yes_ask`. The normalised probability needs a documented rule
  (last trade → bid/ask midpoint → null).
- Multi-outcome questions are split into one binary market per outcome under one event
  (e.g. `KXOAIANTH-40-ANTH` / `-OAI`). Normalise at market level and keep `event_id`.

---

## 2. Keep / replace / drop

| Area | Decision | Why |
|------|----------|-----|
| FastAPI app, async SQLAlchemy, Pydantic | **Keep** | Matches the target stack and works. Restructured, not rewritten. |
| Next.js frontend, MarketCard UI, dark mode | **Keep**, upgrade Next.js, add ESLint/tsc, swap `polymarket_id` for `source` + `external_id` | The UI is the demo. A visual refactor of the inline styles is not a priority. |
| OpenRouter as LLM gateway | **Keep** | One OpenAI-compatible API gives the fallback model across providers, cost reporting per call, and per-key credit limits (used as the CI hard cost cap). |
| `PolymarketService` | **Replace** with `PolymarketSource` adapter, disabled by default | Becomes one implementation of `MarketSource`. |
| APScheduler in API process | **Replace** with Airflow DAG (Phase 3) | Scheduling belongs outside the web process. |
| Direct writes to `markets` / `market_snapshots` | **Replace** with S3 raw → Postgres `raw` → dbt marts | Raw data is kept unchanged so models can be rebuilt without re-fetching. |
| OpenRouter web-search plugin for grounding | **Replace** with RAG over stored RSS news (Phase 4) | Deterministic, testable, citable and cheaper. The current prompt even forbids citations. |
| `TITLE:/BODY:` text parsing | **Replace** with structured output validated by Pydantic | Removes a fragile parser. |
| `create_all` on startup, gitignored migrations | **Replace** with committed Alembic migrations for app-owned tables | Reproducible schema. |
| `prompt-evaluation/` scripts | **Port** to `evals/` (Phase 5); keep thesis results as a read-only baseline under `evals/baselines/thesis-2026-04/` | The scripts stay reachable at the `v1-thesis` tag; keeping two harnesses would be dead code. |
| `THESIS_PROMPT*.md` (Estonian thesis-writing prompts), `.numbers`, `patch_factual.py` | **Drop from `production`** (kept at the tag) | Thesis-writing artifacts, not project code. |

### Schema ownership (new boundary)

- `raw.*`: written only by ingestion loaders (JSONB payload + metadata). Created by Alembic.
- `staging.*`, `intermediate.*`, `marts.*`: owned only by dbt.
- `app.*` (articles, news embeddings, `llm_calls`, agent query log): owned by the API through Alembic.
- The API reads market data from `marts.*` only. The SQL agent's read-only role sees `marts.*` only.

---

## 3. Places where I suggest deviating from the brief

1. **Package layout.** Separate top-level `api/`, `llm/`, `ingestion/`, `evals/` Python
   directories would mean several packages, path hacks or a workspace. Proposal: one
   installable package with a src layout, plus top-level directories for everything
   that is not Python:
   ```
   src/pmnews/{sources,ingestion,api,llm,agent,evals,core}/
   tests/            dags/            warehouse/ (dbt)
   evals/ (golden set, rubric, results/, baselines/)
   frontend/         infra/           docs/
   ```
   One `pyproject.toml` and one `uv.lock`, with one ruff/mypy config. Module boundaries
   are enforced by import rules (e.g. `api` may import `llm`, `sources` imports nothing app-level).
2. **Airflow in docker compose moves from Phase 1 to Phase 3.** There is no DAG until
   Phase 3, and Airflow adds several GB of RAM. It will sit behind a compose profile
   (`make up` for the app, `make up-pipeline` to add Airflow) so the app stays light.
3. **Phase 1 needs seed data.** The current app only fetches from Polymarket, which is
   blocked here, so a fresh clone would show an empty page. Phase 1 adds `make seed`
   from recorded fixtures; real Kalshi/Manifold data arrives in Phase 2.
4. **Airflow SLAs.** Airflow 3 removed the old SLA feature; the replacement is Deadline
   Alerts. I'll use the current Airflow 3 mechanism (or `execution_timeout` plus a failure
   callback if Deadline Alerts are not stable enough) and note it in the DAG.
5. **Local S3.** MinIO changed how it distributes its community edition in late 2025. In
   Phase 3 I'll check whether a maintained, pinned image is still available. If not, I'll
   use another S3-compatible local server (e.g. `motoserver/moto`). The code only sees
   the S3 API, so this is a one-line compose change.
6. **Embeddings run locally, not through a paid API.** Proposal: `fastembed` (ONNX,
   `bge-small-en-v1.5`, 384 dims). Embedding then costs nothing and is deterministic in
   tests and CI. The trade-off is a larger API image.
7. **AWS shape (Phase 6).** An ALB plus two Fargate services cost more each month than one
   small EC2 instance, before any traffic. Proposal: one EC2 instance running the compose
   stack (Caddy for TLS, API, frontend, Airflow), RDS `db.t4g.micro` in a private subnet,
   no NAT gateway (RDS needs no internet egress; EC2 sits in a public subnet behind a
   tight security group), deploy via SSM Run Command (no SSH keys). Terraform state in S3
   with native S3 lockfile locking (Terraform ≥1.10, no DynamoDB table needed). Region:
   `eu-north-1` (Stockholm, closest to Estonia). Exact monthly cost will be measured with
   the AWS Pricing Calculator in Phase 6, not guessed here.
8. **Public demo and paid calls.** On the live site, article generation will not be
   triggerable by anonymous visitors. Articles are pre-generated by the DAG for the top
   daily movers (with a daily cap), and the generate endpoints require an admin token.
9. **Judge model independence.** In the thesis main pass, the judge (DeepSeek v3.2) was
   also one of the writers, which risks self-preference bias on grammar, clarity, relevance
   and format. The factual scores came from a separate judge (GPT-4o search preview), so
   they are not affected. Production evals use a judge from a different model family than
   the writer for every criterion.
10. **Repository name.** "polymarket-news" is misleading once Polymarket is off by default.
    Consider renaming the GitHub repo (e.g. `prediction-market-news`). GitHub redirects
    the old URL. This is your call; I won't do it.

---

## 4. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **The thesis evals measured a different prompt than the app ships.** `web_writer.py` requires inline citations and a SOURCES list; `services/llm.py` forbids citations. The rubric checks "≤60 words" while both prompts say "<80 words". | Thesis scores cannot be quoted as the score of the deployed app. | README labels thesis numbers as thesis-harness results. Phase 5 evals load the same versioned prompt files the API uses. |
| Two versions of thesis factual scores (original vs grounded-patched CSV, 24/30 rows). | Quoting the wrong one in README/CV. | Resolved: the thesis uses the grounded scores. README states the method and that 6/30 rows kept the original score. |
| LLM-as-judge noise makes the CI gate flaky. | False CI failures or a gate that never fires. | Temperature 0, fixed judge model, threshold with a margin; the deterministic numeric fact-check is the primary gate. |
| Paid LLM calls from public endpoints or loops. | Unbounded spend. | Admin token, per-run caps, dedicated OpenRouter keys with credit limits (CI key = hard cap), and I ask before any paid batch. |
| Kalshi data quality (combo markets, untraded candles, fixed-point strings). | Wrong probabilities in marts. | Normalisation rules in the adapter, dbt tests (0 ≤ p ≤ 1, not-null, freshness). |
| Polymarket fixtures cannot be recorded from Estonia. | Adapter tests rely on hand-written fixtures. | Fixtures written from the response shape the thesis code already parses, clearly marked as synthetic. No circumvention. |
| Terms of use for displaying Kalshi/Manifold data publicly, and for RSS feeds. | Legal/ethical issue on a public demo. | Checked in Phase 2 (docs/data-sources.md): Manifold permits it; news limited to CC BY-ND and public-domain feeds (BBC, Guardian rejected). **Kalshi display terms still unconfirmed — gate for Phase 6.** |
| Cross-platform matching (`mart_cross_platform`) may be sparse. | Mart with few rows. | Embedding similarity + a small hand-curated mapping seed; report the match rate honestly. |
| Airflow + dbt dependency conflicts in one image. | Broken builds. | dbt in its own virtualenv inside the Airflow image, called via a BashOperator. |
| Airflow memory on a small EC2 instance. | OOM on the demo host. | LocalExecutor, a single scheduler, an instance size chosen from measured memory use. |
| New tools (Airflow, dbt, Terraform, AWS). | Defending them in interviews. | Short explanations in code comments, ADRs, and `docs/INTERVIEW_NOTES.md`. |

---

## 5. Phase plan (adjusted)

Every phase ends with a summary and verification commands, and I stop for review.

### Phase 0: Preserve the thesis *(after you answer the questions below)*
- Decide what happens to the uncommitted working-tree changes (see questions).
- `git tag -a v1-thesis` on the final thesis commit, create branch `production`.
- `CHANGELOG.md` with "Thesis (v1-thesis)" and "Post-thesis" sections.

### Phase 1: Clean up and test what exists
- Tooling: `uv` with Python 3.12, `pyproject.toml` + `uv.lock`, `ruff`, `mypy --strict`
  on `src/`, pre-commit with `gitleaks`, `package-lock.json`, `eslint.config.mjs`, `tsc --noEmit`.
- Move backend into `src/pmnews/` (pure move commit first, then refactors, so the diff stays reviewable).
- Upgrade Next.js to a patched release.
- Fix issues 1–9 from §1.4, each as its own `fix:` commit with a regression test.
  (Issue 1 gets an admin-token dependency now; issue 4 becomes a non-blocking startup.)
- Commit an Alembic baseline migration and remove `create_all`.
- pytest + `respx` with recorded fixtures; Postgres-backed tests use a throwaway container
  (`testcontainers`) or the compose DB.
- Compose: `pgvector/pgvector` Postgres, API (prod image, no `--reload`), frontend; `make seed`.
- `Makefile`: `setup`, `up`, `down`, `seed`, `test`, `lint`, `typecheck`, `eval` (stub until Phase 5).
- Fix config drift: one `.env.example`, consistent variable names.
- **Done when:** fresh clone → `make setup && make up && make seed` shows markets; `make test` and `make lint` pass.

### Phase 2: Pluggable market data sources
- `MarketSource` protocol + normalised Pydantic models (`source`, `external_id`, `event_id`,
  `question`, `probability: Decimal`, `volume`, `close_time`, `url`, …) and a source registry
  driven by config (`SOURCES_ENABLED=kalshi,manifold`).
- Kalshi adapter (read-only public market data only), Manifold adapter, Polymarket adapter
  (disabled by default, clean error on timeout), RSS adapter (2–4 feeds after checking terms).
- Shared HTTP client: timeouts, retry with exponential backoff and jitter on 429/5xx,
  `Retry-After` support, per-source rate limit, ETag/conditional requests where supported.
- Raw responses written unchanged to object storage (`s3://…/raw/source=<s>/dt=<date>/…json`).
  Phase 2 uses a local-filesystem backend behind the same interface; S3/MinIO comes in Phase 3.
- **Done when:** each adapter has fixture tests, and switching sources is a config change.

### Phase 3: Airflow + object storage + dbt
- Compose profile `pipeline`: Airflow 3 (LocalExecutor), local S3 server.
- One daily DAG: per-source fetch → land raw JSON → load `raw.*` → `dbt build`.
  Retries, deadline/timeout handling, failure callback (log + optional webhook).
- dbt: staging per source → `int_unified_markets` → marts `mart_daily_movers` (LAG),
  `mart_volatility` (rolling stddev), `mart_market_news`, `mart_cross_platform`.
  Incremental models for price history. Tests: unique, not_null, accepted_values,
  source freshness, custom `probability_between_0_and_1`. `dbt docs generate`.
- Point the API at marts and remove APScheduler.
- SQL showcase: `EXPLAIN (ANALYZE, BUFFERS)` before/after indexes on a realistically
  sized dataset → `docs/sql-performance.md` with measured numbers.
- **Done when:** the DAG runs end to end locally and `dbt build` is green.

### Phase 4: LLM layer in production style
- Versioned prompt files (`src/pmnews/llm/prompts/<name>/v<N>.md`), structured output
  validated by Pydantic, timeouts, retries, fallback model.
- RAG: embed news into pgvector (local `fastembed`), retrieve per market, cite URLs.
- SQL Q&A agent: read-only role, `statement_timeout`, row limit, SQL parsed with `sqlglot`
  (single SELECT only, allow-listed schemas), every query logged.
- `llm_calls` table (model, tokens, cost from OpenRouter usage accounting, latency, status)
  and structured JSON logs.
- **Done when:** both endpoints work locally, with mocked-LLM unit tests passing.

### Phase 5: Evals as a CI gate
- Golden set of 30–50 hand-checked cases (versioned JSONL), built from warehouse data.
  **You** check the cases by hand; I prepare candidates.
- Judge rubric adapted from the thesis, judge from a different model family than the writer.
- Numeric fact-check: extract every number from the article and compare it with the warehouse.
- Agent SQL correctness against expected result sets.
- `make eval` → score table + `evals/results/<date>.json`; CI runs a subset when prompts
  or LLM code change, with a threshold file and a credit-capped key.
- **Done when:** a deliberately worse prompt makes CI fail.

### Phase 6: AWS + Terraform + CI/CD *(I ask before every `apply`)*
- Bootstrap state bucket, then **AWS Budgets alarm as the first resource**.
- S3, RDS (pgvector), ECR, EC2 host (see §3.7), Secrets Manager, CloudWatch logs and
  dashboard, least-privilege IAM, GitHub OIDC role.
- GitHub Actions: PR = lint, typecheck, test, `dbt build` on a service container,
  `terraform fmt/validate/plan`; merge to main = build, push to ECR, deploy.
- **Done when:** a merge deploys and the live URL serves articles.

### Phase 7: Job-application ready
- README, 5–7 ADRs, `docs/CV_BULLETS.md` (EN + ET, measured numbers only, `TODO` where
  not yet measured), `docs/INTERVIEW_NOTES.md`, a final fresh-clone run-through.

### Points where I will stop and ask (money or irreversible)
- Installing local tools with Homebrew (`uv`, `gitleaks`, `pre-commit` now; `terraform`, `awscli` in Phase 6).
- Any LLM run beyond a handful of calls (golden-set generation, full `make eval`).
- Creating the OpenRouter CI key, AWS account setup, every `terraform apply`.
- Pushing the tag/branch to GitHub or renaming the repo.
