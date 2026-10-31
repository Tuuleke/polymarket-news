import json
from datetime import date

import respx

from pmnews.db.models import ArticleType, Market, MarketSnapshot
from pmnews.llm.articles import LLMService


def _market() -> Market:
    return Market(
        polymarket_id="538932",
        question="Will the Federal Reserve hold interest rates unchanged in April 2026?",
        category="finance",
        probability=0.99,
        volume=128_000_000,
        end_date=None,
    )


def test_parse_title_and_body() -> None:
    assert LLMService._parse("TITLE: Headline\nBODY:\nLine one\nLine two") == (
        "Headline",
        "Line one\nLine two",
    )


def test_parse_strips_reasoning_block() -> None:
    raw = "<think>internal notes</think>\nTITLE: Headline\nBODY:\nText"
    assert LLMService._parse(raw) == ("Headline", "Text")


def test_parse_falls_back_to_first_line_and_raw_text() -> None:
    assert LLMService._parse("No markers here") == ("No markers here", "No markers here")


async def test_generate_explanation_sends_market_data(
    llm: LLMService, openrouter: respx.Route
) -> None:
    fields = await llm.generate_explanation(_market())

    assert fields["title"] == "Fed Expected to Hold Rates in April"
    assert fields["article_type"] is ArticleType.explanation
    assert fields["probability_at_generation"] == 0.99
    prompt = json.loads(openrouter.calls.last.request.content)["messages"][1]["content"]
    assert "Current probability: 99%" in prompt
    assert "Trading volume: $128,000,000" in prompt


async def test_generate_update_records_change(llm: LLMService, openrouter: respx.Route) -> None:
    prev = MarketSnapshot(date=date(2026, 4, 7), probability=0.72)
    curr = MarketSnapshot(date=date(2026, 4, 11), probability=0.99)

    fields = await llm.generate_update(_market(), prev, curr)

    assert fields["article_type"] is ArticleType.update
    assert fields["snapshot_date"] == date(2026, 4, 11)
    assert fields["probability_change"] is not None
    assert round(fields["probability_change"], 2) == 0.27
    prompt = json.loads(openrouter.calls.last.request.content)["messages"][1]["content"]
    assert "rose 27.0 percentage points" in prompt
