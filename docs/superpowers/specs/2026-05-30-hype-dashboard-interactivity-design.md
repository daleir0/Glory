---
title: Glory HYPE — Dashboard Interactivity (v3.1)
date: 2026-05-30
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v3.1 (enhancement to v3 chart reader)
builds_on: 2026-05-30-hype-chart-reader-design.md
---

# Glory HYPE — Dashboard Interactivity (v3.1)

## Purpose

Two dashboard enhancements on top of v3:

1. **Drop-to-read** — drop a HYPE chart on the dashboard; it's saved and queued as
   *pending*; the Claude Code agent (the vision engine) reads the saved image and
   finalizes the structured ChartRead, which then renders on the site.
2. **Trade calculator** — a position-sizing + PnL tool: given entry, TP, SL,
   direction, leverage, and an amount, compute the position size, margin, PnL at
   TP/SL, ROI, R:R, an estimated liquidation price, and plain-language suggestions.

Both are manual tools that surface on the dashboard. The v4 decision engine (later)
will consume the chart read and reuse the calculator for auto-sizing.

## Feature A — Drop-to-read

### Flow
```
user drops chart image on dashboard
   → POST /api/chart/upload (multipart)
   → server saves image to charts/hype-<ts>.png, inserts a chart_reads row
     with status="pending" (image_path set, structured fields at defaults)
   → dashboard shows a pending queue ("awaiting Glory's read") with thumbnail
   → agent (in session) lists pending reads, opens the saved image with its
     Read tool, produces the ChartRead JSON, and finalizes it
   → row flips to status="read"; dashboard renders the full analysis
```

The server never runs a vision model — per "use you always", the agent is the reader.
The dashboard is just a smoother intake than pasting into chat.

### Changes
- **`chart_reads` gets a `status` column** (`"pending"` | `"read"`, default `"read"`
  so existing v3 CLI inserts stay "read").
- **`record.py`**: add `finalize_chart_read(store, ts, data)` — updates an existing
  row's structured fields + JSON and sets `status="read"`. Keep `record_chart_read`
  as-is for the direct CLI path (inserts a complete read).
- **Store**: `insert_pending_chart_read(ts, image_path)`, `pending_chart_reads()`,
  `finalize_chart_read(ts, read_dict)`; `latest_chart_read` returns the latest
  `status="read"` row (so a pending upload doesn't blank the panel).
- **Server**: `POST /api/chart/upload` (multipart image → save + pending row),
  `GET /api/chart/pending` (list pending with image_path + ts).
- **CLI**: `chart --pending` (print pending rows as JSON for the agent), and
  `chart --finalize <ts> --file read.json` (finalize a pending read).
- **Dashboard**: a drop zone (drag/drop + file picker) posting to the upload
  endpoint, and a pending-queue display with thumbnails.

### Agent workflow (how a pending read gets read)
1. `python -m glory_hype chart --pending` → lists pending rows (ts + image_path).
2. Agent opens the image at `image_path` with its Read tool, extracts the ChartRead.
3. Agent writes the JSON to a temp file and runs
   `python -m glory_hype chart --finalize <ts> --file read.json`.

## Feature B — Trade calculator

### Module `calc.py` — `compute_trade(params) -> dict`

Pure, deterministic, no I/O. Three input **modes**, all producing the same output set.

**Common inputs:** `entry`, `tp`, `sl`, `direction` ("long"|"short"), `leverage`.

| mode | extra input(s) | derivation |
|------|----------------|------------|
| `margin` | `margin` | `notional = margin × leverage` |
| `position` | `position_notional` | `margin = notional ÷ leverage` |
| `risk_pct` | `account`, `risk_pct` | risk$ = account × risk_pct; `coins = risk$ ÷ |entry−sl|`; `notional = coins × entry`; `margin = notional ÷ leverage` |

**Outputs:**
- `position_notional` (USD), `position_coins` (= notional / entry), `margin` (USD)
- `pnl_at_tp`, `pnl_at_sl` (USD), `roi_tp`, `roi_sl` (= pnl / margin, fraction)
- `rr` (reward:risk = |tp−entry| / |entry−sl|; `None` if risk distance is 0)
- `liq_price` (estimate; long `entry×(1−1/leverage)`, short `entry×(1+1/leverage)`;
  simplified — excludes fees and maintenance margin, labeled as an estimate)
- `suggestions`: list of strings

**PnL math (perp standard):**
- long: `pnl(exit) = position_coins × (exit − entry)`
- short: `pnl(exit) = position_coins × (entry − exit)`
- `pnl_at_tp = pnl(tp)`, `pnl_at_sl = pnl(sl)`

**Suggestions logic:**
- `rr < 1` → "Reward is smaller than risk (R:R {rr}) — unfavorable."
- `rr >= 2` → "Healthy R:R ({rr})."
- SL at/through liquidation (long: `sl <= liq_price`; short: `sl >= liq_price`) →
  "⚠️ Stop is at/beyond estimated liquidation ({liq}) — you'd be liquidated first."
- inverted target for direction (long with `tp <= entry`, or short with `tp >= entry`)
  → "⚠️ TP is on the wrong side of entry for a {direction}." (still computes)
- inverted stop (long with `sl >= entry`, short with `sl <= entry`) → similar warn.
- risk_pct mode with `risk_pct > 0.05` → "Risking >5% of account on one trade is aggressive."

**Validation:** `entry/tp/sl > 0`, `leverage >= 1`, mode-required fields present and
> 0; on invalid input raise `ValueError` (the endpoint maps it to a 400 with the message).

### Server + dashboard
- `POST /api/calc` — JSON body of params → `compute_trade` result (400 on ValueError).
- Dashboard **calculator form**: mode selector, the input fields, a Calculate button,
  and a results panel (position size, margin, PnL at TP/SL in $ and %, R:R, liq price,
  suggestions). Pre-fillable from the latest chart read's `current_price` as entry.

## Architecture / files

```
glory-hype/glory_hype/
  chart/
    record.py        # MODIFY: add finalize_chart_read
  calc.py            # NEW: compute_trade (pure)
  db.py              # MODIFY: status column + pending/finalize Store methods
  server.py          # MODIFY: /api/chart/upload, /api/chart/pending, /api/calc
  static/index.html  # MODIFY: drop zone, pending queue, calculator form
  __main__.py        # MODIFY: chart --pending / --finalize flags
```

New dependency: `python-multipart` (FastAPI needs it for multipart upload). Added to
requirements + pyproject.

## Error handling

- **Upload of a non-image / oversized file** → server validates content-type starts
  with `image/`; on failure returns 400 and does not insert a row.
- **Image save failure** → 500 with message; no pending row inserted (nothing to read).
- **Finalize for a missing ts** → no-op update returns a clear "no pending read at ts"
  (CLI prints it; agent can re-list).
- **Calculator invalid input** → `ValueError` → 400 with the specific message; the
  dashboard shows it inline rather than a broken result.
- **Liquidation/divide-by-zero** (leverage exactly 1 → liq at 0 for long; risk distance
  0 → `rr=None`, and risk_pct mode rejects 0 risk distance with ValueError).

## Verification / success criteria

- Dropping a chart on the dashboard creates a pending row + saved image; the pending
  queue shows it; after the agent finalizes, the Chart panel shows the full read.
- `compute_trade` matches hand-computed PnL/margin/R:R for known examples across all
  three modes (covered by unit tests).
- Calculator suggestions fire on the documented conditions.
- `/api/calc` returns 400 with a useful message on bad input.
- Existing v3 CLI `chart --file` path still inserts a `status="read"` row unchanged.

## Testing

- **Offline-unit:** `compute_trade` across all 3 modes incl. PnL signs for long/short,
  R:R, liq estimate, every suggestion branch, and ValueError paths; `finalize_chart_read`
  (pending → read) and Store pending/finalize methods against a temp DB; `/api/calc`,
  `/api/chart/upload` (with a fake image), and `/api/chart/pending` via `TestClient`.
- The agent's vision step is not unit-tested; the ChartRead contract (from v3) already
  guarantees graceful handling of its output.

## Open questions (resolve in planning, not blocking)

- Upload size cap: reject > 10 MB (a generous screenshot ceiling) to avoid abuse.
- Fees in PnL: v3.1 ignores trading fees/funding in PnL (labeled "gross"); a later
  refinement can subtract taker fees + expected funding.
