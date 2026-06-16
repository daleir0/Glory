---
title: Glory HYPE — Chart Reader (v3)
date: 2026-05-30
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v3 of 5
builds_on: 2026-05-29-hype-narrative-engine-design.md
---

# Glory HYPE — Chart Reader (v3)

## Purpose

The user pastes a HYPE chart screenshot; Glory reads it and extracts a complete,
structured **ChartRead** — *everything visible on the chart* — stored timeline-tied
in `hype.db` (and the image saved for later learning). This becomes the third input
to v4's decision, alongside v1 live market data and the v2 narrative Conclusion.

Per the user's standing decision ("we will use you always"), the **vision engine is
the Claude Code agent itself**: the agent reads the pasted image directly and produces
the ChartRead JSON. v3's *code* is therefore a schema + storage + display layer; the
extraction is the agent. (When v4 needs unattended chart reads, revisit a local
vision model — same pattern as the v2 synthesis decision.)

## Scope of v3

**In scope:** a strict `ChartRead` schema + defensive parser, a `chart_reads` table in
`hype.db`, image persistence to `charts/`, a `record_chart_read` function, a `chart`
CLI command, and a dashboard Chart panel + `/api/chart` endpoint.

**Out of scope:** the v4 decision engine that *consumes* the chart read (next phase),
v5 learning, and any automated/unattended vision model. v3 produces and stores the
read; v4 acts on it.

## The ChartRead schema (the contract)

A strict, defensively-parsed shape so the agent's extractions are consistent across
sessions and v4 can rely on them. "Everything on the chart" is captured via the
structured fields plus a `visible_text` catch-all and the full `raw` blob — nothing
visible is lost.

```
ChartRead:
  # meta
  ts: int                      # epoch ms when recorded
  timeframe: str               # "1m" | "5m" | "1h" | "1d" | ... | "unknown"
  exchange_pair: str           # e.g. "Hyperliquid HYPE-USD" if visible
  price_range_low: float|None
  price_range_high: float|None
  # price structure
  current_price: float|None
  swing_high: float|None
  swing_low: float|None
  trend: str                   # "up" | "down" | "range" | "unknown"
  support_levels: list[float]
  resistance_levels: list[float]
  # patterns & signals
  patterns: list[str]          # "ascending triangle", "breakout", "double top", ...
  signals: list[str]           # candlestick / trendline signals
  # indicators (only those visible)
  indicators: dict             # {"rsi": 72.0, "macd": "bullish cross",
                               #  "moving_avgs": {...}, "volume": "...", ...}
  # position / order overlays if shown on the chart
  position: dict|None          # {"side","entry","size","leverage","liq_price","pnl"}
  orders: list                 # any order/stop/take-profit lines drawn
  # catch-all so NOTHING visible is dropped
  annotations: list[str]       # user-drawn notes/lines/zones
  visible_text: list[str]      # any other text/labels/values read off the image
  notes: str                   # the agent's freeform read of the chart
  # provenance
  image_path: str|None         # saved screenshot for v5 learning
  raw: dict                    # full extraction JSON, auditable
```

## Architecture

A `chart/` subpackage inside `glory-hype`, writing to the same `hype.db` timeline.
Small, single-responsibility units mirroring the v2 pattern.

```
glory-hype/glory_hype/
  chart/
    __init__.py
    chartread.py     # ChartRead dataclass + parse_chart_read (defensive) + to_dict
    record.py        # record_chart_read(store, data, image_bytes=None) -> ChartRead
  db.py              # MODIFY: add chart_reads table + Store methods
  server.py          # MODIFY: add /api/chart (latest read)
  static/index.html  # MODIFY: add Chart panel
  __main__.py        # MODIFY: add `chart` subcommand
  charts/            # saved screenshots (gitignored)
```

### chartread.py

`parse_chart_read(data: dict, ts, image_path)` validates and normalizes the agent's
extraction defensively — coerce types, default missing fields, clamp obvious nonsense
(e.g. drop non-numeric levels) — exactly like `conclusion.parse_conclusion`. A sloppy
or partial extraction yields a valid `ChartRead` with safe defaults rather than a crash
or corrupt row. `to_dict()` round-trips for storage and the API.

### Storage (`chart_reads` table in `hype.db`)

| Column | Type | Notes |
|--------|------|-------|
| `ts` | INTEGER PRIMARY KEY | epoch ms |
| `timeframe` | TEXT | indexed |
| `trend` | TEXT | indexed |
| `current_price` | REAL | indexed |
| `image_path` | TEXT | nullable |
| `json` | TEXT | full ChartRead, JSON |

Store methods (same `self._lock`/WAL discipline as v1/v2): `insert_chart_read`,
`recent_chart_reads(since_ts)`, `latest_chart_read`.

### record.py

`record_chart_read(store, data, image_bytes=None)`:
1. If `image_bytes` given, write to `charts/hype-<ts>.png` and set `image_path`.
2. `parse_chart_read(data, ts, image_path)` → `ChartRead`.
3. `store.insert_chart_read(read.to_dict())`.
4. Return the `ChartRead`.

### CLI `chart`

`python -m glory_hype chart --file read.json [--image path.png]` — loads the JSON the
agent produced (and optional image), records it, prints the stored `ChartRead`. This is
how the agent persists a read during a session.

### Dashboard

`/api/chart` returns the latest read; a Chart panel renders levels, trend, patterns,
indicators, position overlay, and a freshness stamp, with a thumbnail of `image_path`.

## Data flow

```
user pastes HYPE chart screenshot in chat
        │
   agent (Claude) reads the image, extracts ChartRead JSON  ← the vision step
        │
   record_chart_read(store, data, image_bytes)
        │  saves image -> charts/ ; parse_chart_read (defensive)
        ▼
   hype.db: chart_reads  (timeline-tied)
        │
   /api/chart + dashboard Chart panel   (and, in v4, the decision engine)
```

## Error handling

- **Partial/garbage extraction** → `parse_chart_read` returns a valid ChartRead with
  safe defaults (`trend="unknown"`, empty lists, `None` numerics); never crashes or
  writes a corrupt row.
- **Image write failure** → log and proceed with `image_path=None`; the structured read
  still persists (the read is the critical part, the image is a bonus for learning).
- **Bad numeric levels** (non-float entries in level lists) → dropped during parse.
- **Missing timeframe/trend** → default to `"unknown"`.

## Verification / success criteria

- Pasting a real HYPE chart yields a stored `chart_reads` row whose levels/trend/patterns
  match what's visibly on the chart, with the image saved under `charts/`.
- `parse_chart_read` handles valid, partial, and garbage input → always a valid ChartRead.
- `latest_chart_read` round-trips the full JSON (lists/dicts intact).
- Dashboard Chart panel shows the latest read + image thumbnail with a freshness stamp.
- A failed image save still persists the structured read.

## Testing

- **Offline-unit:** `parse_chart_read` (valid / partial / garbage / bad-level-coercion),
  Store insert/read/latest round-trip, `record_chart_read` with fake image bytes (writes
  file + row), and the `/api/chart` endpoint via `TestClient` against a seeded DB.
- The vision step (the agent) is not unit-tested, but the **contract it must produce is**
  — so a bad extraction degrades gracefully instead of corrupting the timeline.

## Open questions (resolve during planning, not blocking)

- Image format/size: store as-pasted (PNG) without re-encoding; cap is the user's
  screenshot size — no resizing in v3.
- Whether to keep every read or dedupe near-identical consecutive reads — default: keep
  all (cheap, and v5 learning benefits from the full history).
