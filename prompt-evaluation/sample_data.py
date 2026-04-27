"""
Real Polymarket markets fetched April 2026.
Volumes and probabilities reflect live market data at time of collection.
Update sample probability moves are grounded in real historical events.
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class SampleMarket:
    question: str
    category: str
    probability: float   # 0–1
    volume: float        # USD


@dataclass
class SampleSnapshot:
    date: date
    probability: float   # 0–1


@dataclass
class SampleUpdate:
    market: SampleMarket
    prev: SampleSnapshot
    curr: SampleSnapshot


# ── Explanation samples ───────────────────────────────────────────────────────
# Source: polymarket.com top markets by volume, April 22 2026

EXPLANATION_SAMPLES: list[SampleMarket] = [
    SampleMarket(
        question="Will France win the 2026 FIFA World Cup?",
        category="Sports",
        probability=0.17,
        volume=734_000_000,
    ),
    SampleMarket(
        question="Will the Oklahoma City Thunder win the 2026 NBA Championship?",
        category="Sports",
        probability=0.52,
        volume=317_000_000,
    ),
    SampleMarket(
        question="Will the Federal Reserve hold interest rates unchanged at its April 2026 meeting?",
        category="Economics",
        probability=0.99,
        volume=128_000_000,
    ),
    SampleMarket(
        question="Will Gavin Newsom be the 2028 Democratic presidential nominee?",
        category="Politics",
        probability=0.25,
        volume=1_000_000_000,
    ),
    SampleMarket(
        question="Will Bitcoin hit $150,000 by December 31, 2026?",
        category="Crypto",
        probability=0.10,
        volume=18_000_000,
    ),
]

# ── Update (change-specific) samples ─────────────────────────────────────────
# All probability moves are grounded in real events. Sources: polymarket.com,
# predictionhunt.com, gncrypto.news, cointrenches.io

UPDATE_SAMPLES: list[SampleUpdate] = [
    SampleUpdate(
        # OKC's Game 1 blowout win (119-84 vs Phoenix) on April 19 drove a big
        # probability jump. Feb 19 base rate confirmed by Polymarket trading data.
        market=SampleMarket(
            question="Will the Oklahoma City Thunder win the 2026 NBA Championship?",
            category="Sports",
            probability=0.52,
            volume=317_000_000,
        ),
        prev=SampleSnapshot(date=date(2026, 2, 19), probability=0.35),
        curr=SampleSnapshot(date=date(2026, 4, 19), probability=0.52),
    ),
    SampleUpdate(
        # Bitcoin dropped from ~$83k in early April to ~$74,726 by April 19,
        # causing the "$80k in April" probability to collapse from ~65% to 31%.
        market=SampleMarket(
            question="Will Bitcoin hit $80,000 in April 2026?",
            category="Crypto",
            probability=0.31,
            volume=39_000_000,
        ),
        prev=SampleSnapshot(date=date(2026, 4, 3), probability=0.65),
        curr=SampleSnapshot(date=date(2026, 4, 19), probability=0.31),
    ),
    SampleUpdate(
        # George Russell's Australian GP pole on March 7 caused odds to surge
        # from 28% to 50% in two days. Source: predictionhunt.com.
        market=SampleMarket(
            question="Will George Russell win the 2026 Formula 1 Drivers' Championship?",
            category="Sports",
            probability=0.43,
            volume=123_000_000,
        ),
        prev=SampleSnapshot(date=date(2026, 3, 5), probability=0.28),
        curr=SampleSnapshot(date=date(2026, 3, 7), probability=0.50),
    ),
    SampleUpdate(
        # Finland won the UMK national final on Feb 8 (Linda Lampenius,
        # "Liekinheitin"), driving a surge from ~18% to ~36% on Polymarket.
        market=SampleMarket(
            question="Will Finland win Eurovision 2026?",
            category="Culture",
            probability=0.36,
            volume=107_000_000,
        ),
        prev=SampleSnapshot(date=date(2026, 2, 1), probability=0.18),
        curr=SampleSnapshot(date=date(2026, 2, 9), probability=0.36),
    ),
    SampleUpdate(
        # March CPI printed 3.3% YoY (up from 2.4% in Feb), driven by energy
        # costs from the Iran conflict. Released ~April 10, probability of Fed
        # hold at April meeting jumped from ~72% to 99%.
        market=SampleMarket(
            question="Will the Federal Reserve hold interest rates unchanged at its April 2026 meeting?",
            category="Economics",
            probability=0.99,
            volume=128_000_000,
        ),
        prev=SampleSnapshot(date=date(2026, 4, 7), probability=0.72),
        curr=SampleSnapshot(date=date(2026, 4, 11), probability=0.99),
    ),
]
