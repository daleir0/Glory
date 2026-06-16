---
title: Glory HYPE — Narrative Engine (v2)
date: 2026-05-29
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v2 of 5
builds_on: 2026-05-29-hype-data-foundation-design.md
---

# Glory HYPE — Narrative Engine (v2)

## Purpose

Continuously gather narrative signal about HYPE from **all** sources, store it
timeline-tied alongside the v1 price data, and on demand fuse it into one
**reliability-weighted conclusion** (directional bias + confidence + drivers).
Explicitly built to become a **mandatory input to v4's pre-trade reasoning** —
Glory weighs "what is the narrative doing to this market" before confirming any
long/short.

Guiding principles carried from v1:
- **Data is the guarantee.** Sources differ in certainty, so the fusion **weights
  by reliability** rather than counting headlines. Noise never overrides fact.
- **Honest by design.** The conclusion exposes its drivers, caution flags, and
  which sources it leaned on — it is auditable, not a black box.
- **Continuous ingest, on-demand synthesis** — cheap raw collection always running;
  the expensive LLM fusion runs only when asked or when v4 needs it.

## Scope of v2

**In scope:** multi-source narrative ingestion (4 source types as pluggable
adapters), normalization + dedupe, timeline-tied storage in `hype.db`, an
on-demand Claude-powered synthesizer that produces a structured weighted
conclusion, a dashboard Narrative panel, and a `narrative` CLI command.

**Out of scope (later phases):** the chart-screenshot reader (v3), the long/short
decision engine that *consumes* this conclusion (v4), track-record/learning (v5),
whale-wallet sourcing (later). v2 produces the conclusion; v4 acts on it.

## Architecture

Lives in the existing `glory-hype` package as a `narrative/` subpackage, writing to
the **same `hype.db`** so every narrative item shares the timeline with
candles/funding/trades. Small, single-responsibility units with clean interfaces.

```
glory-hype/glory_hype/
  narrative/
    __init__.py
    item.py            # NarrativeItem dataclass + content-hash + dedupe
    weights.py         # source reliability weights (config)
    adapters/
      __init__.py
      base.py          # SourceAdapter protocol: fetch() -> list[NarrativeItem]
      news.py          # CryptoPanic / RSS crypto outlets
      websearch.py     # broad web search
      onchain.py       # derived from our own hype.db (funding flips, OI surges, large trades)
      social.py        # best-effort X/sentiment (slot; never blocks others)
    store.py           # narrative_items table read/write + dedupe-on-insert
    ingest.py          # ingest loop: poll all adapters, store new items
    synthesize.py      # on-demand: assemble weighted prompt -> proxy(Claude) -> Conclusion
    proxy_client.py    # thin client for the Glory proxy at localhost:8082
```

### Source adapters (pluggable)

Each adapter implements `SourceAdapter.fetch() -> list[NarrativeItem]` and declares
its `source` name. Adding/swapping a source = adding one file. The four v2 adapters:

| Adapter | Source | Reliability weight | Notes |
|---------|--------|-------------------|-------|
| `onchain` | our own `hype.db` | **1.0** (guaranteed) | funding flips, OI surges, large-trade/liquidation clusters, listings |
| `news` | CryptoPanic / RSS | **0.7** | structured, timestamped |
| `websearch` | web search | **0.6** | broad catch-all (proven in tonight's ATH note) |
| `social` | X / sentiment | **0.3** | best-effort; failure is logged and skipped |

Weights live in `weights.py` and are passed into the synthesis prompt so Claude
discounts low-certainty sources explicitly.

### NarrativeItem (normalized schema)

```
NarrativeItem:
  ts: int                 # epoch ms — ties to the price timeline
  source: str             # "onchain" | "news" | "websearch" | "social"
  reliability_weight: float
  title: str
  body: str               # short summary / content
  url: str | None
  hash: str               # content hash for dedupe
```

### Storage (`narrative_items` table in `hype.db`)

| Column | Type | Notes |
|--------|------|-------|
| `hash` | TEXT PRIMARY KEY | dedupe — repeated headlines insert-or-ignore |
| `ts` | INTEGER | epoch ms, indexed |
| `source` | TEXT | indexed |
| `reliability_weight` | REAL | |
| `title` | TEXT | |
| `body` | TEXT | |
| `url` | TEXT | nullable |

WAL mode (already enabled by v1's `Store`). The narrative store reuses the same DB
file but owns its own table and may use its own `Store`-style class with the same
threading-lock discipline established in v1.

### Synthesizer (on-demand)

1. Pull recent `narrative_items` within a window (default last 24h).
2. Assemble a prompt: the items grouped by source with their reliability weights,
   plus current market context from v1 (`latest_ctx`) so the narrative is read
   against live price/funding/OI.
3. Call **Claude via the proxy** (`localhost:8082`, model routed per CLAUDE.md).
4. Parse the response into a `Conclusion`.

### Conclusion output (the "relative conclusion")

```
Conclusion:
  bias: "bullish" | "bearish" | "neutral"
  confidence: float            # 0.0–1.0
  score: int                   # derived convenience: signed -100..+100
  key_drivers: list[str]       # weighted bullish/bearish factors
  caution_flags: list[str]     # e.g. "parabolic +14% 24h", "whale distribution"
  source_breakdown: dict       # what each source tier contributed
  based_on: list[str]          # item hashes + time window (auditable)
  generated_at: int            # epoch ms
```

`score` is derived (sign from bias, magnitude from confidence) as a single
at-a-glance number for v4; `bias` + `confidence` remain the source of truth.

## Data flow

```
[news][websearch][onchain][social]  --fetch()-->  Normalizer (NarrativeItem + hash)
                                                        |
                                                ingest loop (continuous)
                                                        v
                                          hype.db: narrative_items (deduped)
                                                        |
                                   synthesize (on demand) reads recent window
                                       + v1 latest_ctx, weights by reliability
                                                        v
                                   proxy(Claude) -> Conclusion (bias/confidence/...)
                                                        v
                                   dashboard Narrative panel  +  CLI `narrative`
                                   (and, in v4, the decision engine)
```

## Error handling

- **Any single adapter failing** (especially `social`) is logged and skipped; ingest
  continues with the remaining sources. One dead source never stops the engine.
- **Dedupe**: insert-or-ignore on content `hash`; repeated headlines don't inflate signal.
- **Proxy/Claude unavailable**: synthesizer returns a `Conclusion`-shaped result with
  `bias="neutral"`, `confidence=0.0`, and a `caution_flags=["synthesis unavailable"]`
  rather than raising — v4 can detect and refuse to trade on a missing narrative.
- **Malformed model output**: validate/parse defensively; on parse failure, treat as
  synthesis-unavailable rather than fabricating a conclusion.

## Verification / success criteria

- Ingest loop runs alongside the collector and accumulates deduped `narrative_items`
  from at least the `onchain`, `news`, and `websearch` adapters over a multi-hour run.
- `onchain` adapter produces real events from our own data (e.g. flags an OI surge or
  large-trade cluster that actually occurred) — verifiable against `hype.db`.
- `narrative` CLI returns a structured `Conclusion` whose `key_drivers` and
  `caution_flags` are traceable to stored items (the `based_on` hashes resolve).
- Dashboard Narrative panel shows latest items + last conclusion with a freshness stamp.
- A single failing adapter does not stop ingest (tested).
- Synthesis degrades gracefully when the proxy is down (tested).

## Testing

- **Offline-unit:** `item` hashing/dedupe, `weights`, `onchain` adapter (reads a seeded
  `hype.db`), `store` read/write/dedupe, `Conclusion` parsing, reliability-weighting in
  prompt assembly, and graceful-degradation paths.
- **Mocked-network:** `news` / `websearch` / `social` adapters against canned responses;
  `synthesize` against a mocked `proxy_client`.
- **Opt-in live:** one smoke that ingests a few real items and runs one real synthesis
  through the proxy (marked `live`, deselected by default, like v1).

## Open questions (resolve during planning, not blocking)

- Exact news source: CryptoPanic API (needs a free key) vs. plain RSS of 2–3 outlets.
  Default to RSS if no key, so v2 has zero hard external dependency.
- `onchain` event thresholds (what OI move / trade-cluster size counts as an "event") —
  start conservative, tune against observed data.
- Social access: which realistic feed fills the `social` slot; if none is viable now,
  ship the adapter as a no-op stub that returns `[]` and keep the slot.
