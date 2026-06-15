---
title: Glory HYPE — Track Record + Learning (v5)
date: 2026-05-30
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v5 of 5 (final)
builds_on: 2026-05-30-hype-decision-engine-design.md
---

# Glory HYPE — Track Record + Learning (v5)

## Purpose

Close the loop. Auto-resolve each v4 TradeCall's outcome from our own stored HYPE
candles, compute the **real win-rate / expectancy** from closed trades, and feed that
track record back into the decision context so future calls are informed by what
actually worked. The compounding record **is** the learning — no ML model, consistent
with "we use you for everything."

## Scope of v5

**In scope:** deterministic outcome resolution from v1 candle data, win-rate/expectancy
stats, a resolver that updates open calls, a Track Record dashboard panel + `track` CLI,
and feeding the track summary into the v4 decision context.

**Out of scope:** automated live order execution (v5 measures and learns; it does not
place trades). Any external ML training (the track record itself is the feedback).

## Outcome resolution (the core)

`resolve_outcome(call, candles) -> dict` — pure. `candles` are 1m candles with
`open_ts` strictly after the call's `generated_at`, in ascending time order.

- **Skip:** if `call.decision == "no_trade"` or `tp`/`sl`/`entry` missing → `status="n/a"`.
- **Long:** walk candles in order. For each candle:
  - if `low <= sl` AND `high >= tp` in the *same* candle → **loss** (conservative —
    cannot infer intra-candle order from OHLC), `ambiguous=True`.
  - elif `low <= sl` → **loss**.
  - elif `high >= tp` → **win**.
  - First candle that triggers wins/loses ends the scan.
- **Short:** mirror — `high >= sl` → loss; `low <= tp` → win; straddle → loss/ambiguous.
- **Open:** no candle triggered → `status="open"`.

Output dict: `status` (`win`|`loss`|`open`|`n/a`), `exit_price`, `exit_ts`,
`r_multiple`, `ambiguous`.
- `risk = abs(entry - sl)`, `reward = abs(tp - entry)`.
- win → `r_multiple = round(reward / risk, 4)` (R won), `exit_price = tp`.
- loss → `r_multiple = -1.0`, `exit_price = sl`.
- open / n/a → `r_multiple = None`, `exit_price = None`.

## Stats

`compute_stats(resolved: list[dict]) -> dict` — pure, over resolved outcomes:
- `n_closed` (win+loss), `wins`, `losses`, `open_count`
- `win_rate` = wins / n_closed (None if n_closed == 0)
- `avg_win_r` = mean r_multiple of wins; `avg_loss_r` = mean of losses (= -1.0)
- `expectancy_r` = win_rate*avg_win_r + (1-win_rate)*avg_loss_r (None if no closed)
- `profit_factor` = sum(win R) / abs(sum(loss R)) (None if no losses)

## Resolver

`resolve_open_calls(store) -> dict` (stats after resolving):
1. `store.open_trade_calls()` — calls with `status` in (None, "open") that have a
   decision != no_trade and tp/sl present.
2. For each: `candles = store.candles_since("1m", call["generated_at"])`;
   `outcome = resolve_outcome(call, candles)`.
3. If `outcome["status"]` in ("win","loss"): `store.update_call_outcome(generated_at,
   outcome)` (writes status/exit_price/r_multiple/resolved_at into the row + json).
4. Return `compute_stats(store.recent_trade_calls(since_ts=0))`.

## Architecture / files

```
glory-hype/glory_hype/
  db.py              # MODIFY: trade_calls.status column + migration; open_trade_calls,
                     #         update_call_outcome, candles_since
  track/
    __init__.py
    outcomes.py      # pure: resolve_outcome
    stats.py         # pure: compute_stats
    resolver.py      # resolve_open_calls(store) + track_summary(store)
  decision/engine.py # MODIFY: include track_summary in `inputs` so calls cite the record
  server.py          # MODIFY: /api/track (stats + recent closed)
  static/index.html  # MODIFY: Track Record panel
  __main__.py        # MODIFY: `track` subcommand
  tests/
    test_outcomes.py
    test_track_stats.py
    test_resolver.py
    test_track_server.py
```

### Store changes
- `trade_calls` gains a `status TEXT` column (default `'open'` for calls with a real
  decision; `no_trade` rows are stored with `status='no_trade'`). Guarded migration adds
  the column to existing DBs.
- `open_trade_calls()` → rows with `status='open'`.
- `update_call_outcome(generated_at, outcome)` → set status/exit_price/r_multiple/
  resolved_at in the column(s) and merge into the stored json.
- `candles_since(interval, since_ts)` → `SELECT ... WHERE interval=? AND open_ts > ?
  ORDER BY open_ts`.
- `insert_trade_call` sets `status='no_trade'` when decision is no_trade, else `'open'`.

### Engine change
`record_call` adds `track_summary(store)` output into the `inputs` dict under
`track_record`, so when the agent forms its judgment it can see the live win-rate /
expectancy and weigh it. (The agent's judgment already flows in; this just surfaces the
record alongside the other inputs and stores it for audit.)

### Dashboard
`/api/track` returns `{stats, recent: [closed calls with status/r_multiple]}`. A Track
Record panel shows win-rate, expectancy (R), profit factor, N closed / open, and the
recent closed trades with their R multiples (green win / red loss).

### CLI
`track` → `resolve_open_calls(store)`, print the stats JSON.

## Data flow

```
v4 trade_calls (status=open)
        │  resolve_open_calls
        ▼
candles_since (v1 1m candles)  ──>  resolve_outcome (win/loss/open)
        │
        ▼  update_call_outcome
trade_calls (status=win/loss, r_multiple)
        │  compute_stats
        ▼
/api/track + Track Record panel   AND   track_summary -> next v4 decision context
```

## Error handling

- No candles after a call yet → `status="open"` (nothing to resolve).
- Call missing tp/sl or no_trade → `n/a`, never counted in stats.
- Division by zero guarded: `win_rate`/`expectancy`/`profit_factor` return `None` when
  their denominators are zero (no closed trades / no losses).
- Straddle candle → loss + `ambiguous=True` (conservative, surfaced in the row).
- Resolver is idempotent: re-running only resolves still-open calls; closed calls are
  untouched.

## Verification / success criteria

- A call whose TP is touched by a later candle before SL resolves **win** with the
  correct R; SL-first resolves **loss** (r = −1); neither → **open** (unit-tested for
  long and short, including the straddle → loss case).
- `compute_stats` matches hand-computed win-rate/expectancy/profit-factor for a known
  set of outcomes, and returns `None`s safely on empty/all-open input.
- `resolve_open_calls` updates only open calls, is idempotent, and returns live stats.
- `/api/track` serves stats + recent closed; dashboard panel renders them.
- The next v4 call's `inputs.track_record` carries the current stats.

## Testing

- **Offline-unit:** `resolve_outcome` (long win/loss/open, short win/loss, straddle→loss,
  n/a for no_trade/missing levels); `compute_stats` (known set, empty, all-open, no-losses);
  `resolve_open_calls` + Store `open_trade_calls`/`update_call_outcome`/`candles_since`
  against a seeded temp DB (insert a call + candles that hit TP → becomes win, idempotent
  on re-run); `/api/track` via `TestClient`.
- The agent's judgment remains un-unit-tested; v5 only adds deterministic measurement
  around it.

## Project completion

v5 is the final layer. With it, the system spans: **know the data (v1) → understand the
narrative (v2) → read the chart (v3/3.1) → decide + size (v4) → measure + learn (v5)**,
all grounded in our own guaranteed data and gated for discipline.
