---
title: Glory HYPE — Data Foundation (v1)
date: 2026-05-29
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v1 of 5
---

# Glory HYPE — Data Foundation (v1)

## Purpose

A continuously-running local service that captures **every guaranteed Hyperliquid
fact** about the **HYPE perpetual** and stores it as Glory's permanent, queryable
market memory — with a live dashboard to watch and verify it.

The guiding principle (the user's own framing): **data is the guarantee.** v1 is
purely about *knowing the guaranteed data, completely and continuously.* It makes no
trading decisions. Everything else in the product is built **on top of** this layer.

## Scope of v1

**In scope** — the guaranteed, free, no-auth Hyperliquid native data for HYPE:

- OHLCV candles (1m → 1M), backfilled up to 5,000 bars per interval, then kept live
- Live trade prints (with large-trade flagging)
- Order-book depth snapshots (`l2Book`)
- Funding rate (+ funding history) and funding countdown
- Open interest, mark price, oracle price, mid price, premium
- 24h volume and 24h range / prev-day price

**Out of scope for v1** (committed roadmap below — *deferred, not discarded*):
whale tracking, narratives, the chart-screenshot reader, and the long/short
decision engine.

## Committed Roadmap (each phase builds on the one below)

| Phase | Layer | Notes |
|-------|-------|-------|
| **v1 (this spec)** | **Data Foundation** — guaranteed HYPE data, collector daemon + live dashboard | Everything reads from this; must be complete & continuous first |
| **v2** | **Narratives & context** — news / social / sentiment tied to the timeline | The first "soft" (non-guaranteed) layer. **Must feed into v4's reasoning as a mandatory input — Glory weighs narrative impact before confirming any trade.** |
| **v3** | **Chart-screenshot reader** — paste a HYPE chart → structured levels/structure | Vision pipeline; turns the user's eyes into structured input |
| **v4** | **Decision engine** — fuses v1–v3 → long/short + entry/TP/SL + R:R | The payoff. Reasoning must explicitly account for narrative (v2) before confirming |
| **v5** | **Track record + learning** — logs every call, scores closed trades, computes the **real win% from wins/losses**, feeds outcomes back | Where `agentdb-learning` (Decision Transformer over logged trade trajectories) lands |
| **later** | **Whale tracking** — source top addresses, poll their positions/fills | Lower priority; enrichment layer that can land any time after v1 |

## Architecture (Approach B — decoupled collector + read UI)

Two units, one shared store. The collector is the precious component (it accumulates
the continuous market record); the UI is disposable and can restart freely without
ever punching a gap in the data.

### Unit 1 — Collector daemon (`collector.py`)

- **WebSocket stream** (`wss://api.hyperliquid.xyz/ws`): subscribes to `candle` (1m),
  `trades`, `l2Book`, `activeAssetCtx` for HYPE → writes candles, trade prints, and
  book snapshots in real time.
- **REST poller** (~30–60s, `https://api.hyperliquid.xyz/info`, `type: metaAndAssetCtxs`):
  funding rate, open interest, mark/oracle/mid price, 24h volume, premium → snapshot rows.
- **Backfill on startup** (`candleSnapshot`): up to 5,000 historical candles per tracked
  interval, so we start with history rather than an empty DB.
- **Resilience**: auto-reconnect with backoff, gap detection (compare expected vs.
  received candle timestamps), heartbeat, and structured logging. The data record must
  stay continuous.

### Unit 2 — Read API + dashboard (`server.py` + single page)

- FastAPI, **read-only** against the SQLite store.
- Pushes live updates to the page via SSE.
- Page shows: current price, funding (+ countdown), open interest, 24h range/volume,
  recent large trades, a candle chart, and a **freshness/health indicator**
  (last-tick age, detected gap count) so the data can be trusted at a glance.

### Data store (`hype.db`, SQLite)

| Table | Columns (sketch) |
|-------|------------------|
| `candles` | `interval`, `open_ts`, `o`, `h`, `l`, `c`, `v`, `n` |
| `funding` | `ts`, `rate`, `premium` |
| `market_ctx` | `ts`, `open_interest`, `mark_px`, `oracle_px`, `mid_px`, `day_ntl_vlm`, `prev_day_px` |
| `trades` | `ts`, `px`, `sz`, `side`, `is_large` |
| `book_snapshots` | `ts`, `bids_json`, `asks_json` (top N levels) |

All time-series tables indexed on timestamp. `interval` indexed on `candles`.

## Tech stack

Python + SQLite, matching the existing house style (`glory-core`, the proxy, and the
other `.db` services). Raw `httpx` + `websockets` against the documented endpoints —
no heavyweight SDK dependency, to keep the collector simple and debuggable.

Proposed project location: `E:\Glory\glory-hype\` (adjustable).

## Data flow

```
Hyperliquid API ──┬── WS (candle/trades/l2Book/activeAssetCtx) ──┐
                  └── REST (metaAndAssetCtxs, candleSnapshot) ────┤
                                                                  ▼
                                                          collector.py
                                                                  │  writes
                                                                  ▼
                                                          hype.db (SQLite)
                                                                  │  reads
                                                                  ▼
                                                   server.py (FastAPI + SSE)
                                                                  │
                                                                  ▼
                                                        live dashboard page
```

## Error handling

- **WS disconnect** → exponential-backoff reconnect; on reconnect, REST-backfill any
  candles missed during the outage so gaps self-heal.
- **REST failure / rate-limit** → retry with backoff; log and skip a snapshot rather
  than crash; the WS stream keeps the live picture alive meanwhile.
- **Gap detection** → if candle timestamps skip, record the gap and trigger a targeted
  backfill; surface the gap count on the dashboard health indicator.
- **Bad / malformed payload** → validate shape, log the raw payload, drop the row;
  never let one bad message kill the daemon.

## Verification (how we know it's real)

1. **`verify` command** — pulls the same fields live from Hyperliquid and diffs them
   against the latest stored rows; non-zero diff beyond a tolerance fails.
2. **Dashboard freshness indicator** — last-tick age and gap count visible at all times.
3. **Eyeball check** — dashboard numbers vs. the official HYPE page on the exchange.
4. **Backfill continuity test** — after a forced restart, confirm no candle gap remains.

## Success criteria for v1

- Collector runs as a standalone daemon, survives WS drops, and self-heals candle gaps.
- `hype.db` accumulates continuous candles + funding + market context + trades with no
  unexplained gaps over a multi-hour run.
- Dashboard shows live HYPE data with an honest freshness/health indicator.
- `verify` passes (stored data matches live exchange within tolerance).

## Open questions (to resolve during planning, not blocking)

- "Quarter marks" — confirm the user's intended meaning (quarterly hi/lo? quarter-of-range
  levels? something else) before any layer that needs it.
- Which candle intervals to keep live vs. backfill-only (default: keep 1m/5m/15m/1h/4h/1d).
- Book-snapshot depth N and sampling rate (storage vs. fidelity tradeoff).
