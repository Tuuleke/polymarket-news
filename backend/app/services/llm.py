"""
Service for generating news articles from market data using an LLM.
Uses OpenRouter's OpenAI-compatible API.
"""
import re

from openai import AsyncOpenAI

from app.core.config import settings
from app.db.models import Market, MarketSnapshot


class LLMService:
    """Generates human-readable news articles from prediction market data."""

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
        self._model = settings.LLM_MODEL

    async def generate_explanation(self, market: Market) -> dict:
        """
        Generate an evergreen explanation article for a market.
        Only called when the user presses the 'Generate explanation' button.
        """
        prompt = f"""You are a journalist. Write a brief explanation of this prediction market.

Market: {market.question}
Category: {market.category}
Probability: {market.probability:.0%}
Volume: ${market.volume:,.0f}

Write a headline and a body under 60 words covering what this market predicts, what drives the probability, and how to interpret {market.probability:.0%}.

Format exactly as:
TITLE: <headline>
BODY:
<body>"""

        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
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
        """
        Generate a dated update article about a significant probability move (>15pp).
        Only called when the user presses the 'Generate updates' button.
        """
        direction = "rose" if curr.probability > prev.probability else "fell"
        change_pct = abs(curr.probability - prev.probability) * 100

        prompt = f"""You are a financial journalist. Write a brief update about this prediction market move.

Market: {market.question}
Date: {curr.date}
Move: {prev.probability:.0%} → {curr.probability:.0%} ({direction} {change_pct:.1f}pp)

Write a headline and a body under 60 words covering what happened, likely reasons, and outlook.

Format exactly as:
TITLE: <headline>
BODY:
<body>"""

        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=768,
            messages=[{"role": "user", "content": prompt}],
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
        # Strip <think>...</think> reasoning blocks (Qwen3 thinking mode)
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
