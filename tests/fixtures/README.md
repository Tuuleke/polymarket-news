# Test fixtures

HTTP response bodies replayed with `respx`. Unit tests never touch the network.

| Directory | Origin |
|-----------|--------|
| `polymarket/` | **Synthetic.** Polymarket is not reachable from Estonia, so these were written by hand to match the response fields the thesis code parses (`id`, `question`, `outcomePrices`, `volume`, `endDate`, `clobTokenIds`; CLOB `history[].t/p`). Values are taken from the thesis sample data (April 2026). |
| `openrouter/` | **Synthetic.** Minimal OpenAI-compatible chat-completion bodies. No real model output. |
