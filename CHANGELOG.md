# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Work is split into two eras: the BSc thesis prototype (frozen at the `v1-thesis` tag)
and post-thesis production work on the `production` branch.

## Post-thesis (production)

### Added
- `docs/MIGRATION_PLAN.md`: architecture review and phased plan for the production rebuild.

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
