# Data sources

Every source sits behind the same interface (`pmnews.sources.base.MarketSource`) and maps
into one normalised schema with a `source` column. Which sources run is a configuration
change: `SOURCES_ENABLED=kalshi,manifold` (the default).

All facts below were checked on **2026-10-31** from a machine in Estonia.

## Market platforms

| | Kalshi | Manifold | Polymarket |
|---|---|---|---|
| Default | **on** | **on** | **off** |
| Money | real (US-regulated exchange) | play money ("mana") | real |
| Reachable from Estonia | yes | yes | no (connection timeout) |
| Endpoints used | `GET /events?with_nested_markets=true`, `GET /series/{s}/markets/{t}/candlesticks` | `GET /v0/search-markets`, `GET /v0/bets` | Gamma `GET /markets`, CLOB `GET /prices-history` |
| Authentication | none (public market data only; no account, no trading endpoints) | none | none |
| Our request spacing | ≥ 0.1 s | ≥ 0.15 s (published limit: 500 requests/min per IP) | ≥ 0.2 s |
| Volume unit | contracts traded | mana | USD |
| Daily history | daily candles, dated by US Eastern trading day; bid/ask midpoint on days without trades | last bet of each UTC day, from the latest 1,000 bets | CLOB daily points |

All three share one HTTP client (`pmnews.sources.http.PoliteClient`). It spaces requests,
retries 429/5xx/network errors with exponential backoff and jitter (honouring `Retry-After`),
and sends conditional requests (ETag / Last-Modified).

### Why Polymarket is off by default

Polymarket is not available in Estonia because of its regulatory status, and its APIs
do not respond from there. The adapter is kept, tested on hand-written fixtures, and can be
enabled where access is legal (`SOURCES_ENABLED=kalshi,manifold,polymarket`). When the API
is unreachable it fails like any other source (`SourceError`, HTTP 502 from the API). The
project contains no proxy, VPN or other block-circumvention code.

### Terms of use

- **Manifold**: the [API documentation](https://docs.manifold.markets/api) permits
  "integrations that interact with Manifold", forbids scraping outside the API and
  circumventing rate limits, and requires a licence only for commercial AI training:
  "Academic research, personal projects, and non-commercial use are permitted."
- **Kalshi**: only the public, unauthenticated market-data endpoints are used.
  **Kalshi's terms for displaying this data publicly are not confirmed yet.** This must be
  checked before the public deployment (Phase 6).

## News feeds

Only the title, canonical link, author, publication time and the feed's own summary are
stored (`news_items`). The article text is never fetched. Feeds were chosen by their reuse
terms, not only by reputation:

| Feed | Status | Reason |
|---|---|---|
| [The Conversation](https://theconversation.com/global/articles.atom) | **used** | "publish under a Creative Commons — Attribution/No derivatives licence … you can republish our articles online or in print for free" ([guidelines](https://theconversation.com/republishing-guidelines)). Items are stored unedited, with author and publisher credited. |
| [Federal Reserve press releases](https://www.federalreserve.gov/feeds/press_all.xml) | **used** | "information on Board's website is in the public domain and may be copied and distributed without permission. Please cite to the Board as the source" ([disclaimer](https://www.federalreserve.gov/disclaimer.htm)). |
| BBC News | rejected | Terms of use §15: "You're not allowed to pluck metadata from our content or RSS feeds"; business use needs permission. |
| The Guardian | rejected | Terms: use of Guardian content is "for your own personal and non-commercial use only". |
| NPR | rejected | Terms found only cover podcasts explicitly; reuse of news feeds is unclear. |
| ERR News | rejected for now | Feed states "Eesti Rahvusringhääling" copyright but no licence; would need permission. |
| ECB press releases | rejected for now | Reuse terms could not be confirmed; the feed has no summaries. |

Limitation: two publishers give narrow coverage (strong on economics and academia, weak
on breaking news). Phase 4 retrieval quality depends on this; adding a licensed news API
is listed under next steps.

## Raw landing zone

Every successful response body is written unchanged before parsing, so models can be
rebuilt without calling the APIs again:

```
data/raw/source=<source>/dt=<YYYY-MM-DD>/<endpoint>/<HHMMSS>-<sha256 prefix>.body
                                                    <HHMMSS>-<sha256 prefix>.meta.json
```

`.meta.json` holds the URL, query parameters, status, content type and fetch time. Locally
this is a directory (a Docker volume under compose). Phase 3 adds S3 behind the same
`RawStore` interface.

## Known limitations

- Kalshi lists more than 3,000 open events. Ingestion reads at most `KALSHI_MAX_PAGES`
  (default 10) pages of 200 events and keeps the most traded markets per tab, so very
  active markets outside those pages are missed.
- Manifold history depth depends on activity: busy markets reach back only as far as
  their latest 1,000 bets.
- Volume is not comparable across platforms. It is stored and shown with its unit and
  must not be summed or ranked across sources.
