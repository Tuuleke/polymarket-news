#!/usr/bin/env python3
"""
Grounded factual-consistency re-evaluation.

Reads existing articles from a web_eval JSON file and re-scores only the
factual_consistency dimension using openai/gpt-4o-search-preview, which has
built-in web search — no manual URL fetching needed.

Saves results incrementally so Ctrl+C is safe; resumes from checkpoint on
the next run.

Usage:
    python3 grounded_eval.py                              # default input file
    python3 grounded_eval.py results/web_eval_XYZ.json   # specific file
"""
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Config ─────────────────────────────────────────────────────────────────────

JUDGE_MODEL = "openai/gpt-4o-search-preview"
JUDGE_DELAY_SECS = 1.5

_JUDGE_SYSTEM_PROMPT = """\
You are a strict factual accuracy evaluator for short news articles about \
prediction markets. You have web search capability — use it to verify the \
key factual claims in the article before scoring.

Score factual_consistency on a scale of 0–10:
- 10: Every factual claim is confirmed by web search results
- 7–9: Most claims confirmed, minor unverifiable details
- 4–6: Some claims confirmed, several unverifiable or doubtful
- 1–3: Few claims confirmed, most appear invented or misleading
- 0: Claims actively contradict what web search finds

Rules:
- Search for the specific events, figures, or data mentioned in the article
- A claim is "supported" only if your search results explicitly confirm it
- Probability figures and dates from the market context are given as ground \
  truth — penalise if the article contradicts them
- Return JSON only, no extra text:
  {
    "factual_consistency_grounded": <int 0-10>,
    "supported_claims": ["..."],
    "unsupported_claims": ["..."],
    "reasoning": "<one sentence>"
  }
"""


# ── Judge ──────────────────────────────────────────────────────────────────────

def _build_judge_prompt(article: dict) -> str:
    a_type = article["article_type"]
    market = article.get("market", {})

    if a_type == "explanation":
        ctx = (
            f"Article type: EXPLANATION\n"
            f"Market: {market.get('question', '')}\n"
            f"Category: {market.get('category', '')}\n"
            f"Probability: {market.get('probability', 0):.0%}\n"
            f"Volume: ${market.get('volume', 0):,.0f}"
        )
    else:
        move = article.get("move", {})
        ctx = (
            f"Article type: UPDATE\n"
            f"Market: {market.get('question', '')}\n"
            f"Date: {move.get('date', '')}\n"
            f"Probability moved "
            f"{move.get('prev_probability', 0):.0%} → {move.get('curr_probability', 0):.0%} "
            f"({move.get('direction', '')} {move.get('change_pp', 0)}pp)"
        )

    return (
        f"MARKET CONTEXT (ground truth)\n"
        f"------------------------------\n"
        f"{ctx}\n\n"
        f"ARTICLE TO VERIFY\n"
        f"-----------------\n"
        f"Title: {article.get('title', '')}\n"
        f"Body: {article.get('body', '')}\n\n"
        f"Search the web to verify the factual claims in this article, "
        f"then return your JSON score."
    )


def _parse_judge(raw: str) -> dict:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.MULTILINE).strip()
    raw = re.sub(r"```$", "", raw, flags=re.MULTILINE).strip()
    match = re.search(r"\{[\s\S]+\}", raw)
    if not match:
        return {
            "factual_consistency_grounded": None,
            "supported_claims": [],
            "unsupported_claims": [],
            "reasoning": f"Parse error (no JSON): {raw[:200]}",
        }
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as exc:
        return {
            "factual_consistency_grounded": None,
            "supported_claims": [],
            "unsupported_claims": [],
            "reasoning": f"Parse error ({exc}): {match.group()[:200]}",
        }


async def judge_article(client: AsyncOpenAI, article: dict) -> dict:
    resp = await client.chat.completions.create(
        model=JUDGE_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": _build_judge_prompt(article)},
        ],
    )
    return _parse_judge(resp.choices[0].message.content or "")


# ── Checkpoint ─────────────────────────────────────────────────────────────────

def _write_checkpoint(out_path: Path, eval_results: list[dict]) -> None:
    by_model: dict[str, dict] = {}
    for r in eval_results:
        m = r["writer_model"]
        if m not in by_model:
            by_model[m] = {"orig": [], "grounded": []}
        if r["original_factual_consistency"] is not None:
            by_model[m]["orig"].append(r["original_factual_consistency"])
        if r["grounded_factual_consistency"] is not None:
            by_model[m]["grounded"].append(r["grounded_factual_consistency"])

    def _avg(lst: list) -> float | None:
        return round(sum(lst) / len(lst), 2) if lst else None

    summary_by_model = {}
    for m, d in by_model.items():
        ao, ag = _avg(d["orig"]), _avg(d["grounded"])
        summary_by_model[m] = {
            "avg_original": ao,
            "avg_grounded": ag,
            "avg_delta": round(ag - ao, 2) if (ao is not None and ag is not None) else None,
        }

    all_orig = [r["original_factual_consistency"] for r in eval_results if r["original_factual_consistency"] is not None]
    all_grounded = [r["grounded_factual_consistency"] for r in eval_results if r["grounded_factual_consistency"] is not None]

    out_path.write_text(json.dumps({
        "run_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "judge_model": JUDGE_MODEL,
        "grounding_method": "gpt4o_search_preview",
        "results": eval_results,
        "summary": {
            "by_model": summary_by_model,
            "overall_avg_original": _avg(all_orig),
            "overall_avg_grounded": _avg(all_grounded),
        },
    }, indent=2, default=str))


# ── Main ───────────────────────────────────────────────────────────────────────

async def run(input_path: Path) -> None:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(input_path.read_text())
    client = AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    out_path = input_path.parent / "grounded_eval_results.json"

    # Load existing checkpoint to resume
    eval_results: list[dict] = []
    done: set[tuple[str, str]] = set()
    if out_path.exists():
        try:
            checkpoint = json.loads(out_path.read_text())
            eval_results = checkpoint.get("results", [])
            done = {(r["question"], r["writer_model"]) for r in eval_results}
            print(f"Resuming — {len(done)} article(s) already done, skipping.\n")
        except Exception:
            pass

    for result_block in data["results"]:
        q = result_block["question"]
        a_type = result_block["article_type"]

        print(f"\n── Market: {q[:65]}")

        articles_needed = [
            a for a in result_block["articles"]
            if (q, a.get("writer_model", "?")) not in done
        ]
        if not articles_needed:
            print("  (all articles already evaluated, skipping)")
            continue

        for article in articles_needed:
            model = article.get("writer_model", "?")
            model_short = model.split("/")[-1]
            print(f"  Evaluating [{model_short}]...")

            judge_out = await judge_article(client, article)

            original_fc = (article.get("evaluation", {}).get("scores", {}) or {}).get("factual_consistency")
            grounded_fc = judge_out.get("factual_consistency_grounded")
            delta = (grounded_fc - original_fc) if (grounded_fc is not None and original_fc is not None) else None
            delta_str = f"+{delta}" if delta and delta > 0 else str(delta)
            print(f"    original={original_fc}  grounded={grounded_fc}  delta={delta_str}")

            eval_results.append({
                "article_type": a_type,
                "question": q,
                "writer_model": model,
                "original_factual_consistency": original_fc,
                "grounded_factual_consistency": grounded_fc,
                "delta": delta,
                "supported_claims": judge_out.get("supported_claims", []),
                "unsupported_claims": judge_out.get("unsupported_claims", []),
                "reasoning": judge_out.get("reasoning", ""),
            })
            done.add((q, model))
            _write_checkpoint(out_path, eval_results)

            time.sleep(JUDGE_DELAY_SECS)

    print(f"\nResults saved → {out_path}")

    # ── Summary table ──────────────────────────────────────────────────────────

    final = json.loads(out_path.read_text())
    summary_by_model = final["summary"]["by_model"]

    print(f"\n{'═' * 72}")
    print(f"GROUNDED FACTUAL CONSISTENCY RE-EVALUATION")
    print(f"Judge: {JUDGE_MODEL}")
    print(f"{'─' * 72}")
    print(f"  {'Model':<32}  {'Orig FC':>7}  {'Grounded FC':>11}  {'Delta':>6}  Verdict")
    print(f"{'─' * 72}")

    for m, d in sorted(summary_by_model.items(), key=lambda kv: kv[1]["avg_grounded"] or 0, reverse=True):
        model_short = m.split("/")[-1]
        ao = f"{d['avg_original']:.1f}" if d["avg_original"] is not None else "-"
        ag = f"{d['avg_grounded']:.1f}" if d["avg_grounded"] is not None else "-"
        delta = d["avg_delta"]
        delta_str = (f"+{delta:.1f}" if delta > 0 else f"{delta:.1f}") if delta is not None else "-"
        if delta is None:
            verdict = "n/a"
        elif delta >= 2:
            verdict = "Much higher when grounded"
        elif delta >= 0.5:
            verdict = "Slightly higher when grounded"
        elif delta <= -2:
            verdict = "Much lower when grounded"
        elif delta <= -0.5:
            verdict = "Slightly lower when grounded"
        else:
            verdict = "Roughly the same"
        print(f"  {model_short:<32}  {ao:>7}  {ag:>11}  {delta_str:>6}  {verdict}")

    overall_orig = final["summary"]["overall_avg_original"]
    overall_grounded = final["summary"]["overall_avg_grounded"]
    overall_orig_str = f"{overall_orig:.1f}" if overall_orig is not None else "-"
    overall_grounded_str = f"{overall_grounded:.1f}" if overall_grounded is not None else "-"
    print(f"{'─' * 72}")
    print(f"  {'OVERALL':<32}  {overall_orig_str:>7}  {overall_grounded_str:>11}")
    print(f"{'═' * 72}")


def main() -> None:
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        here = Path(__file__).parent
        input_path = here / "results" / "web_eval_20260423T094539Z.json"

    if not input_path.exists():
        print(f"ERROR: {input_path} not found.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run(input_path))


if __name__ == "__main__":
    main()
