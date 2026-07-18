---
title: Glory HYPE — Pattern Intelligence Engine (v9)
date: 2026-06-03
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v9 (intelligence layer — independent of v6-v8 execution track; improves calls NOW)
builds_on: 2026-05-30-hype-decision-engine-design.md
---

# Glory HYPE — Pattern Intelligence Engine (v9)

## Purpose

Mine the full HYPE trading history we already hold (546 daily + 5,119 hourly candles +
235k market-ctx snapshots, back to launch) to find the **recurring structures that
precede moves** — so Glory knows which way the market is likely to sway *before* it
happens, and feeds that as a real, evidence-backed confidence number into v4 decisions.

Philosophy (user's words): *"We will know which way the market will sway before it
happens. Data gives us that foundation, that gift."* The mandate is to **understand the
data**, not curve-fit it. A pattern only earns trust if it holds **out-of-sample**.

This layer improves manual calls immediately — it does **not** depend on the v6-v8
execution track, so it runs in parallel while the portfolio grows to the $100 automation
milestone.

## Decisions locked (from brainstorming)

- **Three analytical layers:** regime classification → event detection → predictive stats.
- **Patterns are both hand-coded AND auto-discovered**, validated against each other.
- **Live signal threshold: 60%** historical confidence to fire a signal into v4.
- Analysis runs on **1h candles** (full history); 5m used only for entry-timing refinement.
- No external data required — we have everything.

## The anti-overfitting contract (non-negotiable)

A pattern is only used live if ALL hold:
1. **Minimum occurrences:** ≥ 10 historical instances. Fewer = "observed, not trusted."
2. **Out-of-sample validation:** history split into **train (older 70%)** and **test
   (newer 30%)**. Patterns are discovered/tuned on train, then their stats are reported
   on test. A pattern whose edge collapses on test is flagged `unstable` and excluded
   from live signals.
3. **Leak-free labeling:** forward outcomes use ONLY data available at decision time. The
   feature window ends strictly before the outcome window begins.
4. **Confidence intervals, not point estimates:** report win-rate as `p ± 95% CI` (Wilson
   interval). A pattern with 80% win-rate over 10 samples (CI 49-94%) is honestly weaker
   than 70% over 50 (CI 56-81%). The live confidence uses the **lower CI bound**, not the
   point estimate — we under-promise.

## Architecture / files

```
glory-hype/glory_hype/
  patterns/
    __init__.py
    indicators.py   # pure: feature vector for a candle window
    regime.py       # pure: classify window -> trending_up/down/ranging/coiling
    library.py      # hand-coded named patterns (predicate fns over features)
    discover.py     # auto-discovery: cluster pre-move windows -> named patterns
    backtest.py     # walk history: label regimes, detect events, match, score, persist
    detector.py     # live: current state -> active pattern matches + confidence
  db.py             # MODIFY: regimes, pattern_events, pattern_stats, discovered_patterns
  decision/engine.py# MODIFY: pull detector signal -> confidence modifier + inputs
  server.py         # MODIFY: /api/patterns (current regime + matches + stats)
  static/index.html # MODIFY: Pattern Signal panel
  __main__.py       # MODIFY: `patterns analyze` (backtest+discover), `patterns now`
  config.py         # MODIFY: thresholds (MIN_OCCURRENCES, SIGNAL_CONF, train/test split)
```

### indicators.py (pure)
`features(window, ctx_window) -> dict` over a list of candles + aligned funding/OI:
- `price_slope` (linreg slope over N), `dist_from_high_20`, `dist_from_low_20`
- `oi_delta_pct` (OI change over window), `funding_mean`, `funding_sign`,
  `funding_compression` (|funding| near zero)
- `vol_ratio` (window volume / 14d avg), `atr_pct` (volatility), `range_pct`
- `body_ratio`, `wick_asymmetry` (candle structure)
Pure, fully unit-testable on crafted windows.

### regime.py (pure)
`classify(features) -> str` → `trending_up | trending_down | ranging | coiling`.
Coiling = low vol_ratio + funding_compression + flat slope (the pre-expansion state).
Deterministic thresholds (in config), unit-tested.

### library.py (hand-coded patterns)
Each pattern is `(name, predicate(features)->bool, hypothesis_direction)`. Seeded from
the domain knowledge we've already observed in this project:
- `COIL_EXPANSION` — coiling regime + funding compression → big move imminent (direction
  from break)
- `ETF_CATALYST_BREAKOUT` — range-break + OI surge + vol spike → continuation up
- `UNLOCK_FEAR_DUMP` — funding falling + OI falling + sell pressure ahead of a known
  unlock date → down
- `BLOWOFF_TOP` — parabolic slope + vol climax + far above 20-high → reversal down
- `MEAN_REVERSION_BOUNCE` — −7%+ from recent high + funding still positive + OI intact → up
- `CAPITULATION_LOW` — sharp drop + funding flips negative + vol climax → bounce
Hand-coded patterns are scored against history exactly like discovered ones — domain
knowledge proposes, **data decides**.

### discover.py (auto-discovery)
1. Find every historical window preceding a **≥4% move within the next 6h** (both
   directions), on the TRAIN split.
2. Featurize each pre-move window (indicators.py).
3. Cluster the feature vectors (k-means, k chosen by silhouette; standardized features).
4. Each cluster with ≥ MIN_OCCURRENCES becomes a `discovered_pattern` with an
   auto-generated descriptive name (from its dominant features, e.g.
   `disc_lowvol_oibuild_fundflat`).
5. Compute its forward-outcome stats on TRAIN, then **validate on TEST**.

### backtest.py
Walks the full 1h history once:
- labels each bar's `regime`
- detects `pattern_events` (every ≥4% move + its preceding regime + the pattern(s) that
  matched the pre-window)
- computes forward outcomes (next 4h / 12h / 24h % move) leak-free
- writes `pattern_stats` (per pattern: n, win_rate ± CI on train AND test, avg_move_pct,
  avg_move_hrs, direction, `stable` flag)

### detector.py (live)
`current_signal(store) -> dict`: pull the latest ~24h of 1h candles + ctx, compute
features + regime, match hand-coded + discovered patterns, return the active matches
ranked by **lower-CI confidence**, filtered to `stable` patterns ≥ SIGNAL_CONF (0.60).

### v4 integration (decision/engine.py)
`record_call` calls `detector.current_signal(store)` and:
- adds `pattern_signal` to the call's `inputs` (auditable)
- if a stable pattern ≥0.60 **agrees** with the judgment's direction → confidence
  modifier up (capped); if it **conflicts** → modifier down, and if conflict is strong
  (≥0.70 opposite) → add a caution / consider gating. The agent's judgment still leads;
  the pattern signal sharpens or checks it.

### Storage (hype.db)
- `regimes(ts, timeframe, label, features_json)`
- `pattern_events(ts, pattern_name, source[hand|disc], direction, features_json, fwd_4h, fwd_12h, fwd_24h)`
- `pattern_stats(pattern_name, source, n_train, n_test, win_rate_train, win_lo_test, win_hi_test, avg_move_pct, avg_move_hrs, direction, stable)`
- `discovered_patterns(name, centroid_json, dominant_features_json, created_at)`

### Dashboard
**Pattern Signal panel:** current regime, active pattern matches with lower-CI confidence
+ expected direction/size, and a one-line "history says" (e.g. "COIL_EXPANSION — 78%→
lower-CI 64% — avg +5.2% in 6h, n=23"). Decision panel shows the modifier applied.

### CLI
- `patterns analyze` → run backtest + discovery, persist all stats (the heavy offline job)
- `patterns now` → print current regime + live matches

## Data flow

```
18mo history (1h candles + ctx)
   │  backtest.py (one-time / re-runnable)
   ├─ regime labels ─────────────► regimes
   ├─ event detection + features ─► pattern_events
   ├─ hand-coded match + discover ─► discovered_patterns
   └─ forward outcomes + CI + train/test ─► pattern_stats (stable flag)
                                              │
live: detector.current_signal ◄───── pattern_stats (stable, ≥0.60)
                                              │
                                   v4 record_call: confidence modifier + inputs.pattern_signal
                                              │
                                   Decision panel + Pattern Signal panel
```

## Error handling

- Insufficient history for a pattern (< MIN_OCCURRENCES) → excluded from live, logged.
- Pattern stable on train but not test → `stable=False`, never fires live.
- Detector with no qualifying match → returns `{regime, matches: []}`; v4 modifier = 0
  (neutral — patterns only *add* confidence when present, never block a sound judgment by
  their absence).
- Missing/sparse ctx alignment for a window → that window skipped, not guessed.
- k-means failure / degenerate clusters → discovery yields zero discovered patterns; the
  hand-coded library still functions.

## Verification / success criteria

- `indicators` + `regime` produce correct values on crafted windows (unit-tested).
- `backtest` on the real history produces `pattern_stats` with non-empty hand-coded +
  discovered patterns, each carrying train/test split stats and a `stable` flag.
- At least one pattern demonstrates **out-of-sample edge** (test lower-CI > 0.55) — if
  *none* do, that is an honest finding we report, not a number we fabricate.
- `detector.current_signal` returns the live regime + any stable matches.
- A v4 call's `inputs.pattern_signal` reflects the live match; confidence shifts in the
  documented direction when a stable pattern agrees/conflicts.
- Dashboard Pattern panel renders regime + matches.

## Testing

- **Offline-unit:** `indicators`, `regime`, each hand-coded `library` predicate, the
  Wilson-CI helper, forward-outcome labeling (leak-free), train/test split logic,
  detector matching/filtering, v4 modifier math. All pure, deterministic on fixtures.
- **Integration (seeded DB):** run `backtest` on a synthetic 200-bar history with a known
  planted pattern → confirm it's detected, scored, and flagged stable.
- **Real-data smoke (`live`-ish, opt-in):** run `patterns analyze` on the actual hype.db
  and assert it completes and writes stats (no correctness assertion on the numbers —
  they're empirical).

## Out of scope for v9

- ML price *forecasting* models (Decision Transformer etc.) — this is statistical pattern
  matching, not a learned price predictor. (That's a candidate v10 once we have more data
  and real fills.)
- Cross-asset / BTC-correlation features — HYPE-only for now.
- Auto-trading on signals — v9 informs calls; execution stays v6-v8 track.

## Why this is honest, not fortune-telling

We do not claim to predict the future. We measure **how often a given setup was followed
by a given move in the actual past, with out-of-sample validation and confidence
intervals**, and we surface the *lower bound* of that estimate. When the data has no edge,
we say so. That discipline is the entire difference between an edge and a delusion.
