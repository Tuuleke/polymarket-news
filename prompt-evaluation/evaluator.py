"""
LLM-based article evaluator.

Each generated article is scored on five criteria by the evaluator model:
  1. grammar              – correct grammar, punctuation, and spelling (0–10)
  2. factual_consistency  – claims are grounded in real events (judge uses web search) (0–10)
  3. clarity              – easy to understand for a general audience (0–10)
  4. relevance            – stays on-topic, covers the required points (0–10)
  5. format               – title present, body within ~60 words, correct structure (0–10)

The evaluator returns a JSON object with integer scores and a brief rationale.
"""
import json
import re

from openai import AsyncOpenAI

from config import EvalConfig

_EVALUATION_SYSTEM_PROMPT = """\
You are a rigorous editorial evaluator for a financial news service that writes \
short articles about prediction market events.

You will receive:
- The original prompt given to the article-generation model
- The generated article (title + body)
- Contextual facts (market question, probability figures, dates, etc.)

Before scoring, use web_search to verify the key factual claims in the article \
(e.g. game outcomes, economic data, news events). Search at least once. \
Then score the article on each of the five criteria below using integers from 0 to 10 \
(10 = perfect, 0 = completely failed). Be strict and consistent.

CRITERIA
--------
1. grammar (0–10)
   - Zero tolerance for grammatical errors, misspellings, or incorrect punctuation.
   - Deduct points for run-on sentences, comma splices, subject-verb disagreement, etc.

2. factual_consistency (0–10)
   - Use web_search to verify key factual claims in the article (game results,
     economic data releases, news events, etc.).
   - Penalise invented or hallucinated facts that search results contradict.
   - The article must also not contradict figures given in the prompt (probabilities,
     dates, direction of movement).
   - Speculation framed clearly as speculation is acceptable; penalise only if
     speculation is stated as certain fact.

3. clarity (0–10)
   - A general-audience reader should be able to understand the article without prior
     knowledge of prediction markets.
   - Prefer plain language; penalise unnecessary jargon or confusing sentence structure.

4. relevance (0–10)
   - For EXPLANATION articles: must cover (a) what the market predicts, (b) what drives
     the probability, and (c) how to interpret the given probability figure.
   - For UPDATE articles: must cover (a) what happened, (b) plausible reasons (framed
     as speculation), and (c) outlook.
   - Deduct points for off-topic content or omitted required points.

5. format (0–10)
   - Title must be present and concise (headline style, not a full sentence).
   - Body must be approximately 60 words or fewer (allow ±10 words).
   - Must follow the TITLE / BODY structure requested in the prompt.

OUTPUT FORMAT (strict JSON, no extra text)
------------------------------------------
{
  "scores": {
    "grammar": <int>,
    "factual_consistency": <int>,
    "clarity": <int>,
    "relevance": <int>,
    "format": <int>
  },
  "total": <int>,          // sum of the five scores (0–50)
  "rationale": {
    "grammar": "<brief note>",
    "factual_consistency": "<brief note>",
    "clarity": "<brief note>",
    "relevance": "<brief note>",
    "format": "<brief note>"
  },
  "overall_verdict": "<one sentence summary of the article quality>"
}
"""


def _build_evaluation_prompt(generated: dict) -> str:
    article_type = generated["article_type"]
    title = generated["title"]
    body = generated["body"]
    prompt = generated["prompt"]

    if article_type == "explanation":
        context = (
            f"Article type: EXPLANATION\n"
            f"Market: {generated['market']['question']}\n"
            f"Category: {generated['market']['category']}\n"
            f"Probability: {generated['market']['probability']:.0%}\n"
            f"Volume: ${generated['market']['volume']:,.0f}"
        )
    else:
        move = generated["move"]
        context = (
            f"Article type: UPDATE\n"
            f"Market: {generated['market']['question']}\n"
            f"Date: {move['date']}\n"
            f"Probability moved {move['prev_probability']:.0%} → {move['curr_probability']:.0%} "
            f"({move['direction']} {move['change_pp']}pp)"
        )

    word_count = len(body.split())
    return (
        f"ORIGINAL PROMPT\n"
        f"---------------\n"
        f"{prompt}\n\n"
        f"CONTEXT / GROUND TRUTH\n"
        f"----------------------\n"
        f"{context}\n\n"
        f"GENERATED ARTICLE\n"
        f"-----------------\n"
        f"Title: {title}\n"
        f"Body ({word_count} words): {body}\n"
    )


def _extract_json(raw: str) -> dict:
    """Strip markdown code fences and parse the first JSON object found."""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.MULTILINE).strip()
    raw = re.sub(r"```$", "", raw, flags=re.MULTILINE).strip()
    # Find the first {...} block
    match = re.search(r"\{[\s\S]+\}", raw)
    if not match:
        raise ValueError(f"No JSON object found in evaluator response:\n{raw}")
    return json.loads(match.group())


class ArticleEvaluator:
    def __init__(self, cfg: EvalConfig):
        self._client = AsyncOpenAI(
            api_key=cfg.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self._model = cfg.evaluator_model
        self._max_tokens = cfg.evaluator_max_tokens

    async def _call(self, messages: list[dict]) -> str:
        """Tool-call loop identical to WebSearchWriter — runs until no tool_calls."""
        for _ in range(8):
            resp = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=messages,
                tools=[{"type": "openrouter:web_search"}],
                tool_choice="auto",
            )
            choice = resp.choices[0]
            msg = choice.message

            assistant_turn: dict = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_turn["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_turn)

            if not msg.tool_calls:
                return msg.content or ""

            for tc in msg.tool_calls:
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": ""})

        return msg.content or ""

    async def evaluate(self, generated: dict) -> dict:
        """
        Evaluate a single generated article dict (as returned by WebSearchWriter).
        Returns the original dict enriched with an 'evaluation' key.
        """
        user_prompt = _build_evaluation_prompt(generated)
        raw = await self._call([
            {"role": "system", "content": _EVALUATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        try:
            evaluation = _extract_json(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            evaluation = {
                "error": str(exc),
                "raw_evaluator_output": raw,
                "scores": {},
                "total": None,
                "rationale": {},
                "overall_verdict": "Evaluation failed – see error.",
            }

        result = dict(generated)
        result["evaluation"] = evaluation
        result["evaluator_model"] = self._model
        return result
