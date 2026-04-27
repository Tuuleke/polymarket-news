#!/usr/bin/env python3
"""
Web-Grounded Model Comparison
==============================
3 writer models each write an article on the same topic using web search
(openrouter:web_search).  1 judge model scores all 3 articles.

Writers (all with web search):
    deepseek/deepseek-v3.2
    google/gemini-3-flash-preview
    minimax/minimax-m2.7

Judge:
    deepseek/deepseek-v3.2

Usage
-----
    python3 web_evaluate.py                        # all samples, all types
    python3 web_evaluate.py --type update          # only update articles
    python3 web_evaluate.py --limit 2              # 2 samples per type
    python3 web_evaluate.py --no-save              # print only

Results saved to results/web_eval_<timestamp>.json
"""
import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import EvalConfig, WRITER_MODELS, JUDGE_MODEL
from web_writer import WebSearchWriter
from evaluator import ArticleEvaluator
from sample_data import EXPLANATION_SAMPLES, UPDATE_SAMPLES


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

async def _run_one_sample(
    writers: list[WebSearchWriter],
    evaluator: ArticleEvaluator,
    article_type: str,
    sample,
) -> dict:
    """All writers work on the same sample in parallel, then the judge scores each."""
    question = sample.question if article_type == "explanation" else sample.market.question
    print(f"  [{article_type}] {question[:65]}")

    if article_type == "explanation":
        write_coros = [w.write_explanation(sample) for w in writers]
    else:
        write_coros = [w.write_update(sample.market, sample.prev, sample.curr) for w in writers]

    articles = await asyncio.gather(*write_coros)
    print(f"    → judging {len(articles)} articles …")
    judged = await asyncio.gather(*[evaluator.evaluate(a) for a in articles])

    return {
        "article_type": article_type,
        "question": question,
        "articles": list(judged),
    }


async def _run(
    cfg: EvalConfig,
    article_types: list[str],
    limit: int | None,
    out_paths: dict | None = None,
) -> list[dict]:
    writers = [
        WebSearchWriter(model=m, api_key=cfg.openrouter_api_key)
        for m in WRITER_MODELS
    ]
    evaluator = ArticleEvaluator(cfg)

    work: list[tuple[str, object]] = []
    if "explanation" in article_types:
        for s in (EXPLANATION_SAMPLES[:limit] if limit else EXPLANATION_SAMPLES):
            work.append(("explanation", s))
    if "update" in article_types:
        for s in (UPDATE_SAMPLES[:limit] if limit else UPDATE_SAMPLES):
            work.append(("update", s))

    print(f"Running {len(work)} sample(s) × {len(WRITER_MODELS)} writers …\n")
    results = []
    for i, (article_type, sample) in enumerate(work, 1):
        print(f"[{i}/{len(work)}]", end=" ")
        r = await _run_one_sample(writers, evaluator, article_type, sample)
        results.append(r)
        _print_results([r])
        if out_paths:
            _save_all(results, out_paths)

    return results


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_CRITERIA = ["grammar", "factual_consistency", "clarity", "relevance", "format"]
_CRIT_SHORT = {"grammar": "Gra", "factual_consistency": "Fac", "clarity": "Cla",
               "relevance": "Rel", "format": "Fmt"}


def _print_results(results: list[dict]) -> None:
    for r in results:
        print(f"\n{'═' * 76}")
        print(f"  {r['article_type'].upper()} | {r['question'][:68]}")
        print(f"{'─' * 76}")
        print(f"  {'MODEL':<32} TOT  " + "  ".join(_CRIT_SHORT[c] for c in _CRITERIA))
        print(f"{'─' * 76}")

        ranked = sorted(
            r["articles"],
            key=lambda a: a.get("evaluation", {}).get("total") or 0,
            reverse=True,
        )
        for i, article in enumerate(ranked):
            ev = article.get("evaluation", {})
            scores = ev.get("scores", {})
            total = ev.get("total", "?")
            model_short = article.get("writer_model", "?").split("/")[-1][:30]
            rank_prefix = f"#{i+1} {model_short}"
            score_cells = "  ".join(f"{scores.get(c, '?'):>3}" for c in _CRITERIA)
            print(f"  {rank_prefix:<32} {str(total):>3}  {score_cells}")

            # Show title + source count
            title = article.get("title", "")[:60]
            n_sources = len(article.get("sources", []))
            print(f"     Title: {title}")
            if n_sources:
                print(f"     Sources cited: {n_sources}")

            verdict = (ev.get("overall_verdict") or "")[:72]
            if verdict:
                print(f"     Judge: {verdict}")


def _summarise(results: list[dict]) -> None:
    """Print overall model ranking across all samples."""
    model_scores: dict[str, list[int]] = {}
    model_criteria: dict[str, dict[str, list[int]]] = {}

    for r in results:
        for article in r["articles"]:
            model = article.get("writer_model", "?")
            ev = article.get("evaluation", {})
            total = ev.get("total")
            scores = ev.get("scores", {})
            if total is not None:
                model_scores.setdefault(model, []).append(total)
            for c in _CRITERIA:
                v = scores.get(c)
                if v is not None:
                    model_criteria.setdefault(model, {}).setdefault(c, []).append(v)

    print(f"\n{'═' * 76}")
    print("OVERALL MODEL RANKING  (judge: " + JUDGE_MODEL + ")")
    print(f"{'─' * 76}")
    print(f"  {'MODEL':<35} AVG/50  " + "  ".join(f"{_CRIT_SHORT[c]:>3}" for c in _CRITERIA))
    print(f"{'─' * 76}")

    ranked = sorted(
        model_scores.items(),
        key=lambda kv: sum(kv[1]) / len(kv[1]) if kv[1] else 0,
        reverse=True,
    )
    for rank, (model, totals) in enumerate(ranked, 1):
        avg = sum(totals) / len(totals)
        crit_avgs = "  ".join(
            f"{sum(model_criteria.get(model, {}).get(c, [0])) / max(len(model_criteria.get(model, {}).get(c, [1])), 1):>3.0f}"
            for c in _CRITERIA
        )
        print(f"  #{rank} {model:<33} {avg:>6.1f}  {crit_avgs}")

    # Web grounding summary
    print(f"{'─' * 76}")
    print("SOURCES CITED PER ARTICLE")
    for model in [m for m, _ in ranked]:
        all_articles = [
            a for r in results for a in r["articles"]
            if a.get("writer_model") == model
        ]
        source_counts = [len(a.get("sources", [])) for a in all_articles]
        avg_sources = sum(source_counts) / len(source_counts) if source_counts else 0
        zero_sources = sum(1 for c in source_counts if c == 0)
        model_short = model.split("/")[-1][:33]
        print(f"  {model_short:<35} avg {avg_sources:.1f} sources  "
              f"({zero_sources}/{len(source_counts)} articles with no sources)")
    print(f"{'═' * 76}")


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _flat_rows(results: list[dict]) -> list[dict]:
    """Flatten results into one row per article for CSV / markdown export."""
    rows = []
    for r in results:
        for article in r["articles"]:
            ev = article.get("evaluation", {})
            scores = ev.get("scores", {})
            def _s(v) -> str:
                return "" if v is None else str(v)

            rows.append({
                "article_type":       article.get("article_type", ""),
                "market_question":    r["question"],
                "writer_model":       article.get("writer_model", ""),
                "title":              article.get("title", ""),
                "sources_cited":      len(article.get("sources", [])),
                "grammar":            _s(scores.get("grammar")),
                "factual_consistency":_s(scores.get("factual_consistency")),
                "clarity":            _s(scores.get("clarity")),
                "relevance":          _s(scores.get("relevance")),
                "format":             _s(scores.get("format")),
                "total":              _s(ev.get("total")),
                "verdict":            ev.get("overall_verdict", "") or "",
            })
    return rows


def _write_csv(path: Path, results: list[dict]) -> None:
    rows = _flat_rows(results)
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV  saved → {path}")


def _write_markdown(path: Path, results: list[dict]) -> None:
    """
    Two markdown tables:
      1. Per-article scores (every row = one article)
      2. Model summary (averaged across all samples)
    """
    rows = _flat_rows(results)
    lines: list[str] = []

    # ── Table 1: per-article ──────────────────────────────────────────────
    lines += [
        "## Results per article\n",
        "| # | Type | Market | Model | Gra | Fac | Cla | Rel | Fmt | **Total** | Sources |",
        "|---|------|--------|-------|-----|-----|-----|-----|-----|-----------|---------|",
    ]
    for i, row in enumerate(rows, 1):
        model_short = row["writer_model"].split("/")[-1]
        question_short = row["market_question"][:45].replace("|", "\\|")
        lines.append(
            f"| {i} | {row['article_type']} | {question_short} | {model_short} "
            f"| {row['grammar']} | {row['factual_consistency']} | {row['clarity']} "
            f"| {row['relevance']} | {row['format']} | **{row['total']}** "
            f"| {row['sources_cited']} |"
        )

    # ── Table 2: model summary ─────────────────────────────────────────────
    model_data: dict[str, dict] = {}
    for row in rows:
        m = row["writer_model"]
        if m not in model_data:
            model_data[m] = {c: [] for c in _CRITERIA}
            model_data[m]["total"] = []
            model_data[m]["sources"] = []
        for c in _CRITERIA:
            v = row.get(c)
            if v not in ("", None):
                model_data[m][c].append(float(v))
        if row["total"] not in ("", None):
            model_data[m]["total"].append(float(row["total"]))
        model_data[m]["sources"].append(float(row["sources_cited"]))

    def avg(lst: list) -> str:
        return f"{sum(lst)/len(lst):.1f}" if lst else "-"

    ranked_models = sorted(
        model_data.items(),
        key=lambda kv: sum(kv[1]["total"]) / len(kv[1]["total"]) if kv[1]["total"] else 0,
        reverse=True,
    )

    lines += [
        "\n## Model summary (averages)\n",
        "| Rank | Model | Gra | Fac | Cla | Rel | Fmt | **Avg/50** | Sources/article |",
        "|------|-------|-----|-----|-----|-----|-----|------------|-----------------|",
    ]
    for rank, (model, data) in enumerate(ranked_models, 1):
        model_short = model.split("/")[-1]
        lines.append(
            f"| {rank} | {model_short} "
            f"| {avg(data['grammar'])} | {avg(data['factual_consistency'])} "
            f"| {avg(data['clarity'])} | {avg(data['relevance'])} "
            f"| {avg(data['format'])} | **{avg(data['total'])}** "
            f"| {avg(data['sources'])} |"
        )

    lines += [
        "",
        f"*Judge model: {JUDGE_MODEL}*",
        f"*Criteria scored 0–10 each; total 0–50*",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD   saved → {path}")


# ---------------------------------------------------------------------------
# Incremental save (called after every sample)
# ---------------------------------------------------------------------------

def _save_all(results: list[dict], out_paths: dict) -> None:
    """Overwrite all three output files with the results collected so far."""
    json_path: Path = out_paths["json"]
    json_path.write_text(json.dumps({
        "run_at":        out_paths["timestamp"],
        "writer_models": WRITER_MODELS,
        "judge_model":   JUDGE_MODEL,
        "results":       results,
    }, indent=2, default=str))
    _write_csv(out_paths["csv"], results)
    _write_markdown(out_paths["md"], results)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Web-grounded model comparison")
    parser.add_argument("--type", choices=["explanation", "update", "all"], default="all")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max samples per article type")
    parser.add_argument("--output", default=None,
                        help="Base filename inside results/ (without extension, default: auto-timestamped)")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    cfg = EvalConfig()
    cfg.evaluator_model = JUDGE_MODEL

    if not cfg.openrouter_api_key:
        print("ERROR: OPENROUTER_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    article_types = ["explanation", "update"] if args.type == "all" else [args.type]

    out_paths = None
    if not args.no_save:
        out_dir = Path(cfg.results_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stem = args.output or f"web_eval_{timestamp}"
        out_paths = {
            "timestamp": timestamp,
            "json": out_dir / f"{stem}.json",
            "csv":  out_dir / f"{stem}.csv",
            "md":   out_dir / f"{stem}.md",
        }
        print(f"Saving incrementally to results/{stem}.[json|csv|md]\n")

    results = asyncio.run(_run(cfg, article_types, args.limit, out_paths))

    _summarise(results)

    if out_paths:
        print(f"\nFinal files:")
        print(f"  JSON saved → {out_paths['json']}")
        print(f"  CSV  saved → {out_paths['csv']}")
        print(f"  MD   saved → {out_paths['md']}")


if __name__ == "__main__":
    main()
