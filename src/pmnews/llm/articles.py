"""
Service for generating news articles from market data using an LLM.
Uses OpenRouter's OpenAI-compatible API with optional web search.
"""
import re
from datetime import date

from openai import AsyncOpenAI

from pmnews.core.config import settings
from pmnews.db.models import Market, MarketSnapshot

_SYSTEM_PROMPT = """\
You are a financial journalist writing for a general audience with no background \
in prediction markets or finance. Your job is to make complex market data \
understandable and accessible.

Rules:
- Search for recent news before writing. Ground every factual claim in what you find.
- If your searches return nothing relevant, write "Recent coverage of this topic is \
limited" — do not speculate or invent facts.
- Write in plain English. Avoid jargon. Explain what probabilities mean in everyday \
terms (e.g. "roughly a 1-in-4 chance").
- Do NOT include sources, URLs, or citations of any kind.
- Do NOT mention that you searched the web, when the search was conducted, or \
reference search results explicitly. Write as if you simply know the facts.
- Body must be under 80 words.
- Output format must be exactly:
  TITLE: <headline>
  BODY:
  <body>\
"""


class LLMService:
    """Generates human-readable news articles from prediction market data."""

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
        self._model = settings.LLM_MODEL
        self._web_search = settings.LLM_WEB_SEARCH

    def _extra(self) -> dict:
        if self._web_search:
            return {"plugins": [{"id": "web"}]}
        return {}

    async def generate_explanation(self, market: Market) -> dict:
        today = date.today().isoformat()
        end_line = (
            f"Resolves: {market.end_date.date() if hasattr(market.end_date, 'date') else market.end_date}\n"
            if market.end_date else ""
        )

        user_prompt = (
            f"Today is {today}. Search for recent news about this topic, "
            f"then write a brief explanation for a general reader.\n\n"
            f"Market: {market.question}\n"
            f"Category: {market.category}\n"
            f"Current probability: {market.probability:.0%}\n"
            f"Trading volume: ${market.volume:,.0f}\n"
            f"{end_line}"
            f"\nYour body must cover:\n"
            f"1. What this market is asking and what resolves it\n"
            f"2. What recent news or factors are driving the {market.probability:.0%} probability\n"
            f"3. What {market.probability:.0%} means in plain English "
            f"(frame it as a chance, e.g. roughly X-in-10)\n"
        )

        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            extra_body=self._extra(),
        )
        title, body = self._parse(resp.choices[0].message.content or "")
        return {
            "title": title,
            "body": body,
            "llm_model": self._model,
            "probability_at_generation": market.probability,
            "article_type": "explanation",
            "probability_change": None,
            "snapshot_date": None,
        }

    async def generate_update(
        self,
        market: Market,
        prev: MarketSnapshot,
        curr: MarketSnapshot,
    ) -> dict:
        direction = "rose" if curr.probability > prev.probability else "fell"
        change_pct = abs(curr.probability - prev.probability) * 100

        user_prompt = (
            f"Search for news from around {curr.date} that explains this prediction "
            f"market move, then write a brief update for a general reader.\n\n"
            f"Market: {market.question}\n"
            f"Probability on {prev.date}: {prev.probability:.0%}\n"
            f"Probability on {curr.date}: {curr.probability:.0%} "
            f"({direction} {change_pct:.1f} percentage points)\n\n"
            f"Your body must cover:\n"
            f"1. What event or news around {curr.date} caused this move\n"
            f"2. What this shift means for the market's outlook\n\n"
            f"If you cannot find news that explains the move, say so explicitly "
            f"rather than guessing."
        )

        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            extra_body=self._extra(),
        )
        title, body = self._parse(resp.choices[0].message.content or "")
        return {
            "title": title,
            "body": body,
            "llm_model": self._model,
            "probability_at_generation": curr.probability,
            "article_type": "update",
            "probability_change": curr.probability - prev.probability,
            "snapshot_date": curr.date,
        }

    @staticmethod
    def _parse(raw: str) -> tuple[str, str]:
        """Parse 'TITLE: ...\nBODY:\n...' format from LLM output."""
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        lines = raw.strip().splitlines()
        title = ""
        body_lines: list[str] = []
        in_body = False
        for line in lines:
            if line.startswith("TITLE:"):
                title = line.removeprefix("TITLE:").strip()
            elif line.startswith("BODY:"):
                in_body = True
            elif in_body:
                body_lines.append(line)
        body = "\n".join(body_lines).strip()
        return title or (lines[0] if lines else "Untitled"), body or raw
