---
title: Glory HYPE — Decision Engine (v4)
date: 2026-05-30
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v4 of 5
builds_on: 2026-05-30-hype-dashboard-interactivity-design.md
---

# Glory HYPE — Decision Engine (v4)

## Purpose

Fuse the three layers — v1 live market data, the v2 narrative Conclusion, and the
v3 latest chart read — into a **decisive, sized TradeCall** (long/short with entry,
TP, SL, position size, R:R) or an explicit **no_trade** when the data doesn't support
a call. This is the payoff layer the whole project built toward.

The agent (Claude) is the decision brain (per "we will use you always"): the agent
produces the directional judgment + rationale. Deterministic code owns the parts that
must not be left to vibes — the **hard gates**, **position sizing** (via the v3.1
calculator), R:R/liquidation, and storage. **A failed gate overrides the agent's call
to `no_trade`.**

## Responsibility split

| Concern | Owner |
|---------|-------|
| Gather the 3 inputs (ctx, conclusion, chart read) | code |
| Hard gates (stale/flagged/conflicting → no_trade) | code |
| Direction, entry/TP/SL selection, confidence, rationale | agent |
| Position sizing (risk-% mode) + R:R + liquidation | code (calculator) |
| Persist + display | code |

## Hard gates → `no_trade`

The engine returns `no_trade` (recording why) when ANY gate fails:
- **Chart divergence-flagged** — the latest chart read has non-empty `flags`.
- **Narrative unavailable** — latest Conclusion has `confidence == 0` / `bias` neutral
  due to synthesis failure (caution_flags contains "synthesis unavailable").
- **Narrative stale** — Conclusion `generated_at` older than 6h.
- **Live ctx stale** — latest `market_ctx.ts` older than 5 min (collector down).
- **No chart read** — no chart read on record (nothing to anchor entry/TP/SL).
- **R:R < floor** — computed reward:risk below `MIN_RR` (config, default 1.0).
- **Liquidation inside the stop** — est. liq price between entry and SL (you'd be
  liquidated before the stop) — surfaced by the calculator.

Gates are checked on the actual stored data, deterministically.

## Inputs the agent reasons over

When gates pass, the agent receives the fused context and produces a judgment:
- live ctx: mark, funding, OI, 24h range/vol, prev-day
- narrative Conclusion: bias, confidence, score, drivers, caution flags
- chart read: trend, support/resistance, patterns, position/levels (entry/TP/SL if
  the user already has orders on the chart), current price
The agent outputs: `decision` (long/short), `entry`, `tp`, `sl`, `confidence` (0-1),
`rationale` (cites each input and how it was weighed). Entry/TP/SL are anchored on the
chart read's levels when present; otherwise derived from structure + ctx.

## Sizing — risk-% mode, account set on the dashboard

Sizing uses the v3.1 calculator's `risk_pct` mode so a stop-out loses exactly the
configured risk. The account balance, risk %, and leverage are **settings stored in
`hype.db`** and **settable on the dashboard** (not just config), so the user can update
them live:
- `account_balance` (USD), `risk_pct` (default 0.01 = 1%), `leverage` (default 10).
- The calculator form and the decision engine both read these settings.

## TradeCall schema

```
TradeCall:
  decision: "long" | "short" | "no_trade"
  entry, tp, sl: float | None
  position_notional, position_coins, margin, leverage: float | None
  rr: float | None
  liq_price: float | None
  confidence: float            # 0.0–1.0 (0 for no_trade)
  rationale: str               # weighted reasoning citing each input
  gates_failed: list[str]      # empty if a call was made
  inputs: dict                 # {ctx_ts, conclusion_at, chart_read_ts} — auditable
  generated_at: int            # epoch ms
```

## Architecture / files

```
glory-hype/glory_hype/
  config.py            # MODIFY: MIN_RR, default risk/leverage, staleness thresholds
  db.py                # MODIFY: settings table (get/set) + trade_calls table + methods
  decision/
    __init__.py
    gates.py           # pure: evaluate_gates(ctx, conclusion, chart_read, now, cfg) -> list[str]
    tradecall.py       # TradeCall dataclass + parse/validate (defensive, like conclusion)
    engine.py          # gather inputs + gates + size (calculator) + persist; record_call(store, agent_judgment)
  calc.py              # (reused as-is for sizing)
  server.py            # MODIFY: /api/decision (latest), /api/settings (GET/POST)
  static/index.html    # MODIFY: Decision panel + account/risk/leverage settings inputs
  __main__.py          # MODIFY: `decide` subcommand
```

### gates.py (pure)
`evaluate_gates(ctx, conclusion, chart_read, now_ms, cfg) -> list[str]` returns the list
of failed-gate reasons (empty = all pass). Pure and fully unit-testable with crafted
inputs (stale ctx, flagged chart, low R:R, etc.).

### engine.py
`record_call(store, judgment)`:
1. Gather `latest_ctx`, `latest_conclusion`, `latest_chart_read`.
2. `evaluate_gates(...)`. If any fail → store + return a `no_trade` TradeCall with
   `gates_failed`.
3. Else size via `calc.compute_trade(risk_pct mode, account/risk/leverage from settings,
   entry/sl from judgment)`; compute rr/liq; if the calculator's own checks add a fatal
   flag (e.g. liq inside stop, R:R < floor) → downgrade to `no_trade`.
4. Build the TradeCall, persist to `trade_calls`, return it.
The **agent** supplies `judgment` = {decision, entry, tp, sl, confidence, rationale}.

### Storage
- `settings` table: `key TEXT PRIMARY KEY, value TEXT`. Methods `get_setting(key, default)`,
  `set_setting(key, value)`, `get_settings()`.
- `trade_calls` table: `generated_at INTEGER PK, decision TEXT, json TEXT`. Methods
  `insert_trade_call`, `latest_trade_call`, `recent_trade_calls`.

### Dashboard
- **Settings row**: account balance, risk %, leverage inputs → `POST /api/settings`
  (persisted); the calculator pre-fills from these.
- **Decision panel**: latest TradeCall — decision (color-coded), entry/TP/SL, size,
  R:R, liq, confidence, rationale, and (if no_trade) the failed gates in red.

## Data flow

```
v1 ctx ┐
v2 conclusion ├─ gather ─> gates (code) ─ fail ─> no_trade (records why)
v3 chart read ┘                 │pass
                                ▼
                  agent judgment (direction/entry/tp/sl/conf/rationale)
                                ▼
                  size via calculator (settings: account/risk/leverage)
                                ▼
                     TradeCall -> trade_calls -> dashboard Decision panel
                                ▼
                          (v5 will score outcomes)
```

## Error handling

- Any missing input → the corresponding gate fires → `no_trade` (never a call on
  partial data).
- Malformed agent judgment → `tradecall.parse` defaults defensively; if entry/sl can't
  be resolved, `no_trade` with reason "incomplete judgment".
- Settings unset → fall back to config defaults (account required; if account unset/0,
  sizing gate → `no_trade` with "set account balance").
- Calculator `ValueError` → caught → `no_trade` with the message.

## Verification / success criteria

- With aligned inputs (fresh ctx, valid conclusion, unflagged chart, R:R ≥ floor), the
  engine returns a sized long/short call whose size makes a stop-out lose ~risk_pct of
  the account, with a rationale citing all three inputs.
- Each gate independently forces `no_trade` (unit-tested): flagged chart, stale narrative,
  stale ctx, missing chart read, R:R < floor, liq-inside-stop, account unset.
- Settings set on the dashboard persist and change both the calculator and the next call's
  sizing.
- Dashboard Decision panel renders the call (and no_trade reasons).

## Testing

- **Offline-unit:** `evaluate_gates` (every gate branch + all-pass), `tradecall.parse`
  (valid/partial/garbage), `engine.record_call` with seeded store across scenarios
  (call vs each no_trade), settings get/set + trade_calls store round-trip, `/api/decision`
  + `/api/settings` via `TestClient`. Sizing correctness leans on the already-tested calc.
- The agent's directional judgment is not unit-tested; the gates + sizing + schema that
  wrap it are, so a bad judgment degrades to a disciplined no_trade rather than a reckless call.

## Out of scope (v5)

Logging closed-trade outcomes, computing the real win-rate, and feeding results back to
improve calls — that is v5 (track record + learning).
