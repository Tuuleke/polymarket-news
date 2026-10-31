# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Work is split into two eras: the BSc thesis prototype (frozen at the `v1-thesis` tag)
and post-thesis production work on the `production` branch.

## Post-thesis (production)

### Added
- `docs/MIGRATION_PLAN.md`: architecture review and phased plan for the production rebuild.
- pytest suite (36 tests): real Postgres via testcontainers, HTTP mocked with respx,
  migration drift check.
- Alembic migrations (baseline + timestamptz), run by a one-shot `migrate` compose service.
- `make setup | up | seed | test | lint | typecheck | dev`; pre-commit with gitleaks,
  ruff and mypy.
- `make seed`: the 8 thesis sample markets, so a fresh clone shows data.
- `GENERATION_MODE` (`disabled` / `open` / `token`) and `X-Admin-Token` guard on
  endpoints that make paid LLM calls; `MAX_UPDATES_PER_REQUEST` cap.
- `POLYMARKET_ENABLED` flag, off by default (Polymarket is not available in Estonia).
- Pagination (`limit`/`offset`, max 100) on market and article lists.

### Changed
- Backend moved to a `src/pmnews` package managed with uv; `mypy --strict` and ruff clean.
- Services are injected with FastAPI dependencies instead of module-level singletons.
- Next.js 15.2.0 → 16.4.3 (security advisories), ESLint flat config, `tsc --noEmit`,
  Inter self-hosted via `next/font`, lockfile committed.
- Docker images install from lockfiles and run as non-root users; compose uses the
  pgvector Postgres image and binds ports to 127.0.0.1.

### Fixed
- Price-history `since` used a non-portable, local-time timestamp.
- Naive and local-time datetimes; snapshot dates are now UTC calendar days.
- Unparseable prices were stored as 0% instead of being skipped.
- Snapshot insert count reported attempted rows.
- API startup blocked on the first fetch (about two minutes when Polymarket is unreachable).
- Missing OpenRouter key surfaced as an opaque 500.
- `GET /markets` returned the full, ever-growing snapshot history.
- Alembic's logging setup disabled the application's loggers.

## Thesis (v1-thesis)

Snapshot of the project as submitted for the TalTech BSc thesis
"Tehisintellektil põhineva uudisteplatvormi arendamine ennustusturgude andmete
kättesaadavuse parandamiseks". Browse it at the
[`v1-thesis`](https://github.com/Tuuleke/polymarket-news/tree/v1-thesis) tag.

### Added
- FastAPI backend that fetches Polymarket markets on a schedule and stores daily
  probability snapshots in PostgreSQL.
- LLM-generated "explanation" and "update" articles via OpenRouter with web search.
- Next.js frontend with market cards, sparklines, sorting and dark mode.
- `prompt-evaluation/`: LLM-as-judge comparison of three writer models
  (DeepSeek v3.2, Gemini 3 Flash preview, MiniMax M2.7) on 10 cases, plus a grounded
  re-scoring pass for factual consistency. The thesis reports the grounded factual scores
  (`results/web_eval_20260423T094539Z.csv`, patched by `results/patch_factual.py`).

### Notes
- `docs/MIGRATION_PLAN.md` was committed in the final thesis commit by accident;
  it is post-thesis work.
