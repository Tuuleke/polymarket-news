"""
Web-search-enabled article writer.

Uses openrouter:web_search (server-side tool) so the model can search for
April 2026 news before writing. The tool-call loop runs until the model
produces a final answer or the round limit is hit.
"""
import re
from openai import AsyncOpenAI

from sample_data import SampleMarket, SampleSnapshot, SampleUpdate

_WRITER_SYSTEM_PROMPT = """\
You are a financial journalist. Today's date is April 2026.

Before writing any article you MUST use the web_search tool at least twice to \
find recent news (March–April 2026) relevant to the topic. Search for specific \
events, announcements, or data that explain the current situation.

Rules:
- Every factual claim must be grounded in search results.
- Cite sources inline with numbered references: [1], [2], etc.
- End with a SOURCES section listing the full URLs.
- Body must be under 80 words (not counting the SOURCES section).
- If your searches return no relevant results, state this explicitly \
  rather than speculating.
"""

_WEB_SEARCH_TOOL = {"type": "openrouter:web_search"}


def _normalise(line: str) -> str:
    """Strip markdown bold/italic markers so **TITLE:** and *BODY:* are recognised."""
    return re.sub(r"\*+", "", line).strip()


def _parse(raw: str) -> tuple[str, str, list[str]]:
    """Extract TITLE / BODY / SOURCES from model output."""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    lines = raw.strip().splitlines()
    title, body_lines, source_lines = "", [], []
    section = None
    for line in lines:
        s = _normalise(line)
        if s.startswith("TITLE:"):
            title = s.removeprefix("TITLE:").strip()
            section = "title"
        elif s.startswith("BODY:"):
            section = "body"
        elif s.startswith("SOURCES:"):
            section = "sources"
        elif section == "body":
            body_lines.append(line)
        elif section == "sources" and s:
            source_lines.append(s.lstrip("-•* "))
    body = "\n".join(body_lines).strip()
    return title or (lines[0] if lines else "Untitled"), body or raw, source_lines


class WebSearchWriter:
    def __init__(self, model: str, api_key: str):
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self._model = model

    async def _call(self, messages: list[dict]) -> str:
        """
        Tool-call loop: keeps going while the model emits tool_calls.
        For openrouter:web_search, OpenRouter executes the search server-side
        and fills in the tool result before continuing — we submit an empty
        content placeholder and it gets resolved on the next round.
        """
        for _ in range(8):
            resp = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=2048,
                messages=messages,
                tools=[_WEB_SEARCH_TOOL],
                tool_choice="auto",
            )
            choice = resp.choices[0]
            msg = choice.message

            # Append assistant turn (include tool_calls if present)
            assistant_turn: dict = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_turn["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_turn)

            if not msg.tool_calls:
                return msg.content or ""

            # Placeholder tool results — OpenRouter resolves web_search server-side
            for tc in msg.tool_calls:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": "",
                })

        return msg.content or ""

    async def write_update(
        self,
        market: SampleMarket,
        prev: SampleSnapshot,
        curr: SampleSnapshot,
    ) -> dict:
        direction = "rose" if curr.probability > prev.probability else "fell"
        change_pct = abs(curr.probability - prev.probability) * 100

        user_prompt = (
            f"Search for recent news (April 2026) about this topic, then write a brief update.\n\n"
            f"Market: {market.question}\n"
            f"Date: {curr.date}\n"
            f"Probability {direction} from {prev.probability:.0%} to "
            f"{curr.probability:.0%} ({change_pct:.1f}pp)\n\n"
            f"Search for events that explain this probability change. "
            f"Write a grounded article citing sources inline.\n\n"
            f"Format exactly as:\n"
            f"TITLE: <headline>\n"
            f"BODY:\n"
            f"<body under 80 words with inline citations [1][2] etc>\n"
            f"SOURCES:\n"
            f"- <url>"
        )

        messages = [
            {"role": "system", "content": _WRITER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        raw = await self._call(messages)
        title, body, sources = _parse(raw)

        return {
            "article_type": "update",
            "writer_model": self._model,
            "raw_output": raw,
            "title": title,
            "body": body,
            "sources": sources,
            "prompt": user_prompt,
            "market": {"question": market.question, "category": market.category},
            "move": {
                "date": str(curr.date),
                "prev_probability": prev.probability,
                "curr_probability": curr.probability,
                "direction": direction,
                "change_pp": round(change_pct, 1),
            },
        }

    async def write_explanation(self, market: SampleMarket) -> dict:
        user_prompt = (
            f"Search for recent news (April 2026) about this topic, "
            f"then write a brief explanation.\n\n"
            f"Market: {market.question}\n"
            f"Category: {market.category}\n"
            f"Current probability: {market.probability:.0%}\n"
            f"Volume: ${market.volume:,.0f}\n\n"
            f"Search for recent developments that explain the current probability. "
            f"Write a grounded explanation citing sources inline.\n\n"
            f"Format exactly as:\n"
            f"TITLE: <headline>\n"
            f"BODY:\n"
            f"<body under 80 words with inline citations [1][2] etc>\n"
            f"SOURCES:\n"
            f"- <url>"
        )

        messages = [
            {"role": "system", "content": _WRITER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        raw = await self._call(messages)
        title, body, sources = _parse(raw)

        return {
            "article_type": "explanation",
            "writer_model": self._model,
            "raw_output": raw,
            "title": title,
            "body": body,
            "sources": sources,
            "prompt": user_prompt,
            "market": {
                "question": market.question,
                "category": market.category,
                "probability": market.probability,
                "volume": market.volume,
            },
        }
