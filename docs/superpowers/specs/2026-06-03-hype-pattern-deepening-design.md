---
title: Glory HYPE — Pattern Engine Deepening (v9.1)
date: 2026-06-03
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v9.1 (deepens v9; v9.2 event-anchored patterns follows before the Jun 6 unlock)
builds_on: 2026-06-03-hype-pattern-intelligence-design.md
---

# Glory HYPE — Pattern Engine Deepening (v9.1)

## Purpose

v9 found no validated edge — by design honesty, but also because it only used
price-shape features against a single 4%/6h move definition. v9.1 gives the search the
inputs that actually move HYPE (funding, OI, large-trade flow), sweeps the move
definition to find *where* edge lives, fixes out-of-sample validation for discovered
patterns, and raises the proof bar with a three-way split + multiple-testing correction.

Principle unchanged: **give the search better inputs while raising the proof standard.**
If it still finds nothing, that is a real finding — we never lower the bar to manufacture
an edge.

## Decisions locked (from brainstorming)

- **Implement all three deepenings:** richer features, multi-threshold/horizon sweep,
  discovered-pattern OOS fix.
- **Strict anti-false-edge:** 3-way split (train/test/holdout 60/20/20) + Benjamini-
  Hochberg FDR at **5%** (tighten to 1% later when we hold more data).
- Event-anchored / catalyst patterns are **v9.2** (separate spec — needs an external
  event catalog) and should follow soon (June 6 unlock is imminent).

## 1. Richer features (`indicators.py`)

Add features from data already in `hype.db` (funding/OI in `market_ctx`, flow in
`trades`), passed in alongside the candle window:

| Feature | Meaning |
|---------|---------|
| `funding_flip` | funding sign changed within the window (bool) |
| `funding_slope` | linreg slope of funding over the window |
| `funding_extreme` | funding z-score vs a trailing distribution |
| `oi_surge` | OI rose ≥ X% vs window start (bool) |
| `oi_drop` | OI fell ≥ X% vs window start (bool) |
| `oi_accel` | second difference of OI (building vs fading) |
| `flow_imbalance` | (large buys − large sells) / total large prints in window |
| `flow_spike` | large-print notional vs trailing baseline |
| `oi_up_price_flat` | OI building while |price_slope| small (coil with fuel) |
| `funding_div` | sign(funding_slope) opposite sign(price_slope) (divergence) |

`features(candles, ctx_rows, trades_rows, vol_avg, oi_baseline, funding_dist)` — extended
signature; all new features default safely when inputs are sparse. Pure, unit-tested.

## 2. Multi-threshold / horizon sweep (`sweep.py` + `backtest.py`)

Define a move across a grid: **thresholds {2,3,5,7}% × horizons {2,6,12,24}h = 16
configs**. For each (pattern × config), compute forward-outcome stats. A pattern is
scored at every config so we discover the config it actually predicts (e.g. COIL → 3%
in 12h, not 4% in 6h). `forward_outcome` already parameterized by threshold; add horizon
as a parameter (candles ahead).

## 3. Discovered-pattern OOS fix (`discover.py` + `backtest.py`)

v9 bug: discovered centroids only ever matched train bars (n_test=0). Fix:
- `assign_to_centroids(vectors, centroids, max_dist)` — assign each TEST and HOLDOUT bar
  to the nearest centroid if within a standardized distance threshold (else unassigned).
- The backtest re-matches every test/holdout bar against the discovered centroids, so
  discovered patterns get real `n_test` / `n_holdout` and can earn a `stable` flag.

## 4. Strict anti-false-edge (the rigor)

### Three-way split
History ordered by time, split **train 60% / test 20% / holdout 20%**. Discovery and
config selection happen on **train**; statistics are measured on **test**; the **holdout
is touched exactly once** for final confirmation and never influences any choice.

### Benjamini-Hochberg FDR
Every (pattern × config) is one hypothesis with a p-value against a no-edge null
(binomial test: is the directional win-rate > 0.5?). Across all hypotheses, apply BH to
control the false-discovery rate at **0.05**. Only BH-significant hypotheses proceed.

### Live-eligibility (all four gates)
A pattern-config fires live only if:
1. **BH-significant** on test (FDR 5%), AND
2. **holds on holdout** (holdout lower-CI ≥ 0.55 — the untouched final check), AND
3. **test lower-CI ≥ 0.60**, AND
4. **≥ 15 occurrences** (test + holdout combined).

`stats.py` gains `binomial_p(wins, n, p0=0.5)` and `benjamini_hochberg(pvalues, q)`.

## Architecture / files

```
glory-hype/glory_hype/patterns/
  indicators.py   # MODIFY: + funding/OI/flow features; extended signature
  stats.py        # MODIFY: + binomial_p, benjamini_hochberg, horizon in forward_outcome
  sweep.py        # NEW: threshold/horizon grid + per-config scoring
  discover.py     # MODIFY: + assign_to_centroids (OOS matching)
  backtest.py     # MODIFY: 3-way split, sweep, BH, holdout, eligibility gates
  detector.py     # MODIFY: read winning-config patterns; match on the new features
glory-hype/glory_hype/
  db.py           # MODIFY: pattern_stats + threshold/horizon/p_value/bh_significant/holdout_lo/n_holdout
  config.py       # MODIFY: sweep grid, FDR_Q, split fractions, OOS distance, gates
```

No new external dependency (numpy/sklearn already added in v9; `scipy` NOT required —
BH and binomial implemented in-package to avoid a heavy dep, both unit-tested).

## Data flow

```
hype.db (candles + ctx + trades, 18mo)
   │  backtest (3-way time split 60/20/20)
   ├─ richer features per window (funding/OI/flow)
   ├─ sweep 16 configs: per (pattern,config) forward outcomes on TEST
   ├─ discover on TRAIN -> centroids -> assign_to_centroids on TEST/HOLDOUT
   ├─ binomial_p per (pattern,config) -> Benjamini-Hochberg @ 0.05
   └─ survivors confirmed on untouched HOLDOUT -> eligibility gates
                         │
                pattern_stats (winning config, p, bh_significant, holdout_lo, stable)
                         │
        detector (live, new features) -> v4 confidence modifier (unchanged interface)
                         │
                dashboard Pattern panel (now shows config + significance)
```

## Error handling

- Sparse trades/ctx for a window → flow/funding features default to neutral (0/False);
  the window is still usable for price features.
- A config with < min occurrences → excluded from BH (not a tested hypothesis).
- BH with zero hypotheses → no survivors, clean empty result.
- Holdout failure after test success → pattern recorded but `stable=0` (test-only edge
  that didn't confirm — exactly what holdout is for).
- Degenerate clusters / no discovered centroids → hand-coded patterns still sweep+score.

## Verification / success criteria

- New features compute correctly on crafted windows incl. funding flip, OI surge, flow
  imbalance (unit-tested).
- `binomial_p` and `benjamini_hochberg` match known textbook values (unit-tested).
- `forward_outcome` honors both threshold and horizon (unit-tested).
- `assign_to_centroids` gives discovered patterns nonzero n_test on a seeded set.
- `backtest` produces `pattern_stats` carrying winning config + p-value + bh_significant +
  holdout_lo; a planted strong pattern in synthetic data survives all four gates; a
  planted noise pattern does NOT.
- Real-data run: report which (pattern, config) survive BH + holdout — honestly, even if
  zero. The deliverable is the validated set (or the validated absence).
- v4 modifier + dashboard still function with the new pattern_stats shape.

## Testing

- **Offline-unit:** new indicators, `binomial_p`, `benjamini_hochberg`, horizon-aware
  `forward_outcome`, `assign_to_centroids`, sweep grid generation, eligibility-gate logic.
- **Integration (synthetic):** plant ONE genuinely-predictive pattern + ONE noise pattern
  in a generated history; assert the real one survives all gates and the noise one is
  filtered by BH/holdout. This is the test that proves the rigor works.
- **Real-data smoke (`live`, opt-in):** run the full sweep on hype.db; print survivors.

## Out of scope (v9.2 / later)

- Event-anchored / catalyst patterns (unlock & ETF dates) — v9.2, needs an event catalog.
- Cross-asset (BTC) features.
- Tightening FDR to 1% — deferred until more data accrues (user decision).
- ML forecasting models.

## Why this is the honest path to edge

v9 proved the discipline; v9.1 proves we can deepen the search *without* loosening it.
Richer inputs raise the chance real structure surfaces; the three-way split + FDR raise
the chance that whatever surfaces is real and not the best of many coin-flips. Edge that
clears this bar is edge we can size into. Edge that doesn't clear it never reaches a
trade — which is exactly how the account survives long enough to compound.
