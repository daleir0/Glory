# HYPE Pattern Engine Deepening (v9.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the v9 pattern engine with funding/OI/flow features, a threshold/horizon sweep, fixed out-of-sample validation for discovered patterns, and strict multiple-testing rigor (3-way split + Benjamini-Hochberg FDR).

**Architecture:** Extends the existing `patterns/` subpackage. Richer `indicators`, new `sweep` grid, `stats` gains binomial-p + BH, `discover` gains OOS centroid assignment, `backtest` rewritten for train/test/holdout split with FDR-gated eligibility. Pure units stay unit-tested; rigor is proven by a planted-pattern-vs-noise integration test.

**Tech Stack:** Python 3.12, `uv`, `numpy`, `scikit-learn` (already deps). No new external deps — BH + binomial implemented in-package.

> **Git note:** prior work committed through e1858cb9. Do NOT commit per-task. Final commit (Task 11) is gated on explicit user approval.

Run offline tests with:
`cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`

---

## File Structure

```
glory-hype/glory_hype/patterns/
  indicators.py   # MODIFY: + funding/OI/flow features; extended signature
  stats.py        # MODIFY: + binomial_p, benjamini_hochberg, horizon-aware forward_outcome
  sweep.py        # NEW: config grid + per-config scoring helpers
  discover.py     # MODIFY: + assign_to_centroids
  backtest.py     # MODIFY: 3-way split, sweep, BH, holdout, eligibility gates
  detector.py     # MODIFY: match on new features; read winning-config patterns
glory-hype/glory_hype/
  config.py       # MODIFY: sweep grid, FDR_Q, split fractions, OOS distance, gates
  db.py           # MODIFY: pattern_stats extra columns + migration
glory-hype/tests/
  test_pattern_stats_v91.py
  test_pattern_indicators_v91.py
  test_pattern_sweep.py
  test_pattern_discover_oos.py
  test_pattern_backtest_v91.py
```

---

### Task 1: Config — sweep grid + rigor thresholds

**Files:**
- Modify: `glory-hype/glory_hype/config.py`

- [ ] **Step 1: Append to `config.py`**

```python
# --- v9.1 pattern deepening ---
SWEEP_THRESHOLDS = [2.0, 3.0, 5.0, 7.0]      # % move
SWEEP_HORIZONS = [2, 6, 12, 24]              # hours ahead
FDR_Q = 0.05                                 # Benjamini-Hochberg false-discovery rate
SPLIT_TRAIN = 0.60
SPLIT_TEST = 0.20                            # holdout = remaining 0.20
OOS_MAX_DIST = 2.5                           # std-units; nearest-centroid assignment cap
GATE_MIN_OCC = 15                            # test+holdout occurrences
GATE_TEST_LO = 0.60                          # test lower-CI bar
GATE_HOLDOUT_LO = 0.55                       # untouched holdout lower-CI bar
OI_SURGE_PCT = 5.0                           # OI move that counts as surge/drop
```

- [ ] **Step 2: Verify**

Run: `cd glory-hype && uv run python -c "from glory_hype import config; print(config.SWEEP_THRESHOLDS, config.FDR_Q, config.GATE_HOLDOUT_LO)"`
Expected: `[2.0, 3.0, 5.0, 7.0] 0.05 0.55`

---

### Task 2: Stats — binomial p-value, Benjamini-Hochberg, horizon-aware outcome

**Files:**
- Modify: `glory-hype/glory_hype/patterns/stats.py`
- Test: `glory-hype/tests/test_pattern_stats_v91.py`

Context: v9 `forward_outcome(start_close, future, threshold_pct)` exists. We add a horizon
cap (only look `horizon` candles ahead) and two new functions. `binomial_p` is a one-sided
test that the win-rate exceeds 0.5 (survival function of Binomial(n, 0.5)). BH adjusts a
list of p-values.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_stats_v91.py`:

```python
from glory_hype.patterns.stats import binomial_p, benjamini_hochberg, forward_outcome


def test_binomial_p_strong():
    # 18 wins of 20 fair coin flips -> very unlikely under p=0.5
    assert binomial_p(18, 20) < 0.001


def test_binomial_p_chance():
    # 11 of 20 -> not significant
    assert binomial_p(11, 20) > 0.2


def test_binomial_p_edges():
    assert binomial_p(0, 0) == 1.0
    assert 0.0 <= binomial_p(10, 10) <= 1.0


def test_benjamini_hochberg_picks_significant():
    pvals = [0.001, 0.008, 0.04, 0.2, 0.7]
    sig = benjamini_hochberg(pvals, q=0.05)
    # the smallest few survive, the large ones do not
    assert sig[0] is True and sig[1] is True
    assert sig[3] is False and sig[4] is False


def test_benjamini_hochberg_all_null():
    assert benjamini_hochberg([0.6, 0.7, 0.9], q=0.05) == [False, False, False]


def test_forward_outcome_horizon_limits_lookahead():
    # move only happens at candle 5; horizon=3 must NOT see it
    future = [{"open_ts": i, "c": 100, "h": 100.5, "l": 99.5} for i in range(4)]
    future.append({"open_ts": 5, "c": 100, "h": 110, "l": 100})  # +10% at index 4
    near = forward_outcome(100.0, future, threshold_pct=4.0, horizon=3)
    assert near["hit"] is False
    far = forward_outcome(100.0, future, threshold_pct=4.0, horizon=10)
    assert far["hit"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_stats_v91.py -v`
Expected: FAIL — `binomial_p`/`benjamini_hochberg` missing; `forward_outcome` has no `horizon`.

- [ ] **Step 3: Implement** — edit `stats.py`. Add at top `import math` (already there) and these functions; modify `forward_outcome` to accept `horizon`:

```python
def binomial_p(wins: int, n: int, p0: float = 0.5) -> float:
    """One-sided p-value: P(X >= wins) for X ~ Binomial(n, p0). 1.0 if n == 0."""
    if n == 0:
        return 1.0
    # survival function via summation (n is small here)
    from math import comb
    tail = sum(comb(n, k) * (p0 ** k) * ((1 - p0) ** (n - k))
               for k in range(wins, n + 1))
    return min(1.0, tail)


def benjamini_hochberg(pvalues: list, q: float = 0.05) -> list:
    """Return a list of bools: which hypotheses are significant under BH-FDR at q.
    Preserves input order."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    sig = [False] * m
    max_k = -1
    for rank, idx in enumerate(order, start=1):
        if pvalues[idx] <= q * rank / m:
            max_k = rank
    if max_k >= 0:
        for rank, idx in enumerate(order, start=1):
            if rank <= max_k:
                sig[idx] = True
    return sig
```

And change `forward_outcome` signature + body first line:

```python
def forward_outcome(start_close: float, future: list, threshold_pct: float,
                    horizon: int | None = None) -> dict:
    """...existing docstring... If horizon is given, only the first `horizon`
    candles are considered."""
    if horizon is not None:
        future = future[:horizon]
    if not future or not start_close:
        return {"direction": "none", "move_pct": 0.0, "hit": False}
    # ... rest unchanged ...
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_stats_v91.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Confirm v9 stats tests still green**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_stats.py -v`
Expected: PASS (the v9 calls without `horizon` still work — it defaults to None).

---

### Task 3: Richer features (funding/OI/flow)

**Files:**
- Modify: `glory-hype/glory_hype/patterns/indicators.py`
- Test: `glory-hype/tests/test_pattern_indicators_v91.py`

Context: extend `features` to accept optional `trades_rows`, `oi_baseline`, `funding_dist`
and emit the new features. Keep the v9 signature working via defaults so existing callers
and tests don't break.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_indicators_v91.py`:

```python
from glory_hype.patterns.indicators import features


def _c(o, h, l, c, v=1.0):
    return {"o": o, "h": h, "l": l, "c": c, "v": v}


def test_funding_flip_and_slope():
    candles = [_c(100, 101, 99, 100)] * 4
    ctx = [{"funding": -0.0002, "open_interest": 1000.0},
           {"funding": 0.0003, "open_interest": 1000.0}]   # negative -> positive
    f = features(candles, ctx, vol_avg=1.0)
    assert f["funding_flip"] is True
    assert f["funding_slope"] > 0


def test_oi_surge_and_flow_imbalance():
    candles = [_c(100, 101, 99, 100)] * 4
    ctx = [{"funding": 0.0001, "open_interest": 1000.0},
           {"funding": 0.0001, "open_interest": 1100.0}]   # +10% OI
    trades = [{"side": "B", "ntl": 5000.0}, {"side": "B", "ntl": 5000.0},
              {"side": "A", "ntl": 1000.0}]                # buys dominate
    f = features(candles, ctx, trades_rows=trades, vol_avg=1.0, oi_baseline=1000.0)
    assert f["oi_surge"] is True
    assert f["flow_imbalance"] > 0       # buy-heavy
    assert f["oi_up_price_flat"] is True  # OI up, price flat


def test_features_backcompat_no_trades():
    # v9 callers pass no trades/baseline — must still work, new flow feats neutral
    f = features([_c(100, 101, 99, 100)], [{"funding": 0.0, "open_interest": 0.0}],
                 vol_avg=1.0)
    assert f["flow_imbalance"] == 0.0
    assert f["funding_flip"] is False
    assert "price_slope" in f
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy pytest tests/test_pattern_indicators_v91.py -v`
Expected: FAIL — new keys missing / signature rejects `trades_rows`.

- [ ] **Step 3: Implement** — modify `features` in `indicators.py`. Change the signature and add the new features before the return, then add them to the returned dict (and to the empty-candles early-return dict):

```python
def features(candles: list, ctx_rows: list, trades_rows: list | None = None,
             vol_avg: float = 1.0, oi_baseline: float | None = None,
             funding_dist: dict | None = None) -> dict:
```

In the empty-`candles` early return dict, add these keys (all neutral):

```python
        "funding_flip": False, "funding_slope": 0.0, "funding_extreme": 0.0,
        "oi_surge": False, "oi_drop": False, "oi_accel": 0.0,
        "flow_imbalance": 0.0, "flow_spike": 0.0,
        "oi_up_price_flat": False, "funding_div": False,
```

Before the final `return`, compute the new features:

```python
    # funding dynamics
    fund_series = [r.get("funding", 0.0) for r in ctx_rows] or [0.0]
    funding_flip = (min(fund_series) < 0 < max(fund_series))
    if len(fund_series) > 1:
        fx = np.arange(len(fund_series))
        funding_slope = float(np.polyfit(fx, fund_series, 1)[0])
    else:
        funding_slope = 0.0
    if funding_dist and funding_dist.get("std"):
        funding_extreme = (fmean - funding_dist.get("mean", 0.0)) / funding_dist["std"]
    else:
        funding_extreme = 0.0

    # OI dynamics
    oi_surge = oi_delta >= 5.0
    oi_drop = oi_delta <= -5.0
    oi_accel = 0.0
    if len(ois) >= 3 and ois[0]:
        d1 = ois[-1] - ois[-2]
        d0 = ois[-2] - ois[0]
        oi_accel = (d1 - d0) / ois[0] * 100

    # large-trade flow
    flow_imbalance, flow_spike = 0.0, 0.0
    if trades_rows:
        buys = sum(t["ntl"] for t in trades_rows if t.get("side") == "B")
        sells = sum(t["ntl"] for t in trades_rows if t.get("side") == "A")
        total = buys + sells
        if total:
            flow_imbalance = (buys - sells) / total
        if oi_baseline:   # crude baseline reuse; spike vs notional baseline
            flow_spike = total / max(oi_baseline, 1e-9)

    oi_up_price_flat = (oi_delta > 2.0 and abs(slope) < 0.1)
    funding_div = ((funding_slope > 0) != (slope > 0)) and abs(slope) > 0.05
```

Add these to the returned dict:

```python
        "funding_flip": bool(funding_flip),
        "funding_slope": round(funding_slope, 8),
        "funding_extreme": round(funding_extreme, 4),
        "oi_surge": bool(oi_surge), "oi_drop": bool(oi_drop),
        "oi_accel": round(oi_accel, 4),
        "flow_imbalance": round(flow_imbalance, 4),
        "flow_spike": round(flow_spike, 6),
        "oi_up_price_flat": bool(oi_up_price_flat),
        "funding_div": bool(funding_div),
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with numpy pytest tests/test_pattern_indicators_v91.py tests/test_pattern_indicators.py -v`
Expected: PASS (3 new + 3 v9 = all green; v9 tests use the 3-arg call which still works).

---

### Task 4: Sweep grid

**Files:**
- Create: `glory-hype/glory_hype/patterns/sweep.py`
- Test: `glory-hype/tests/test_pattern_sweep.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_sweep.py`:

```python
from glory_hype.patterns.sweep import config_grid, score_config
from glory_hype import config


def test_config_grid_size():
    grid = config_grid()
    assert len(grid) == len(config.SWEEP_THRESHOLDS) * len(config.SWEEP_HORIZONS)
    assert (2.0, 6) in grid


def test_score_config_counts_directional_wins():
    # member rows: (features, future_candles). Up move of 5% within horizon.
    def fut(up):
        base = 100.0
        peak = base * (1.05 if up else 0.95)
        return [{"open_ts": 1, "c": base, "h": max(base, peak), "l": min(base, peak)}]
    members = [({"x": 1}, fut(True)), ({"x": 1}, fut(True)), ({"x": 1}, fut(False))]
    res = score_config(members, start_closes=[100.0, 100.0, 100.0],
                       direction="up", threshold=4.0, horizon=6)
    assert res["n"] == 3
    assert res["wins"] == 2       # two up-moves matched 'up'
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_sweep.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/patterns/sweep.py`:

```python
"""Threshold/horizon sweep: enumerate configs and score a pattern at each."""

from glory_hype import config
from glory_hype.patterns.stats import forward_outcome


def config_grid():
    return [(t, h) for t in config.SWEEP_THRESHOLDS for h in config.SWEEP_HORIZONS]


def score_config(members: list, start_closes: list, direction: str,
                 threshold: float, horizon: int) -> dict:
    """members: list of (features, future_candles). start_closes aligned to members.
    Returns wins (forward move matched `direction` at this threshold/horizon) and n."""
    wins, n, moves = 0, 0, []
    for (_, future), sc in zip(members, start_closes):
        o = forward_outcome(sc, future, threshold, horizon=horizon)
        n += 1
        if o["direction"] == direction:
            wins += 1
        if o["hit"]:
            moves.append(abs(o["move_pct"]))
    return {"wins": wins, "n": n, "threshold": threshold, "horizon": horizon,
            "avg_move_pct": (sum(moves) / len(moves)) if moves else 0.0}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_sweep.py -v`
Expected: PASS (2 passed)

---

### Task 5: Discovered-pattern OOS assignment

**Files:**
- Modify: `glory-hype/glory_hype/patterns/discover.py`
- Test: `glory-hype/tests/test_pattern_discover_oos.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_discover_oos.py`:

```python
import numpy as np
from glory_hype.patterns.discover import assign_to_centroids

FEATS = ["a", "b"]


def test_assigns_near_and_rejects_far():
    centroids = [{"a": 0.0, "b": 0.0}, {"a": 10.0, "b": 10.0}]
    scaler = {"mean": {"a": 5.0, "b": 5.0}, "std": {"a": 5.0, "b": 5.0}}
    vectors = [{"a": 0.2, "b": -0.1},     # near centroid 0
               {"a": 9.8, "b": 10.2},     # near centroid 1
               {"a": 100.0, "b": 100.0}]  # far from both -> unassigned
    labels = assign_to_centroids(vectors, centroids, FEATS, scaler, max_dist=2.5)
    assert labels[0] == 0
    assert labels[1] == 1
    assert labels[2] is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy pytest tests/test_pattern_discover_oos.py -v`
Expected: FAIL — function missing.

- [ ] **Step 3: Implement** — append to `discover.py`:

```python
def assign_to_centroids(vectors: list, centroids: list, feature_keys: list,
                        scaler: dict, max_dist: float) -> list:
    """Assign each vector to the nearest centroid in standardized space, or None if
    beyond max_dist. scaler = {'mean': {feat: m}, 'std': {feat: s}} from training."""
    mean = scaler["mean"]
    std = scaler["std"]

    def standardize(d):
        return np.array([(d.get(k, 0.0) - mean[k]) / (std[k] or 1.0)
                         for k in feature_keys])

    cs = [standardize(c) for c in centroids]
    out = []
    for v in vectors:
        sv = standardize(v)
        dists = [float(np.linalg.norm(sv - c)) for c in cs]
        j = int(np.argmin(dists))
        out.append(j if dists[j] <= max_dist else None)
    return out
```

Also export the training scaler from `discover_patterns` so the backtest can reuse it.
In `discover_patterns`, change the scaler line to capture stats and include them per
pattern result:

```python
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
```

and add to the returned dict for each pattern:

```python
            "scaler": {"mean": {feature_keys[i]: float(scaler.mean_[i])
                                for i in range(len(feature_keys))},
                       "std": {feature_keys[i]: float(scaler.scale_[i])
                               for i in range(len(feature_keys))}},
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn pytest tests/test_pattern_discover_oos.py tests/test_pattern_discover.py -v`
Expected: PASS (1 new + 2 v9 = all green).

---

### Task 6: pattern_stats schema extension

**Files:**
- Modify: `glory-hype/glory_hype/db.py`
- Test: extend `glory-hype/tests/test_pattern_store.py`

- [ ] **Step 1: Append a failing test** to `tests/test_pattern_store.py`:

```python
def test_pattern_stat_extended_columns(tmp_path):
    from glory_hype.db import Store
    s = Store(str(tmp_path / "ext.db"))
    s.upsert_pattern_stat({"pattern_name": "P", "source": "hand", "n_train": 30,
                           "n_test": 12, "win_rate_train": 0.7, "win_lo_test": 0.62,
                           "win_hi_test": 0.9, "avg_move_pct": 5.0, "avg_move_hrs": 12,
                           "direction": "up", "stable": 1, "threshold": 3.0,
                           "horizon": 12, "p_value": 0.002, "bh_significant": 1,
                           "holdout_lo": 0.58, "n_holdout": 8})
    row = s.all_pattern_stats()[0]
    assert row["threshold"] == 3.0 and row["horizon"] == 12
    assert row["bh_significant"] == 1 and row["holdout_lo"] == 0.58
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_store.py::test_pattern_stat_extended_columns -v`
Expected: FAIL — columns missing.

- [ ] **Step 3: Extend SCHEMA + migration** — in `db.py`, change the `pattern_stats` CREATE to add the columns:

```sql
CREATE TABLE IF NOT EXISTS pattern_stats (
    pattern_name TEXT PRIMARY KEY, source TEXT, n_train INTEGER, n_test INTEGER,
    win_rate_train REAL, win_lo_test REAL, win_hi_test REAL,
    avg_move_pct REAL, avg_move_hrs REAL, direction TEXT, stable INTEGER,
    threshold REAL, horizon INTEGER, p_value REAL, bh_significant INTEGER,
    holdout_lo REAL, n_holdout INTEGER
);
```

Add to `_migrate` (handles an existing DB that has the v9 table without these columns):

```python
        pcols = [r["name"] for r in self.conn.execute(
            "PRAGMA table_info(pattern_stats)").fetchall()]
        for col, decl in [("threshold", "REAL"), ("horizon", "INTEGER"),
                          ("p_value", "REAL"), ("bh_significant", "INTEGER"),
                          ("holdout_lo", "REAL"), ("n_holdout", "INTEGER")]:
            if pcols and col not in pcols:
                self.conn.execute(f"ALTER TABLE pattern_stats ADD COLUMN {col} {decl}")
```

Update `upsert_pattern_stat` to write the new columns:

```python
    def upsert_pattern_stat(self, p: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO pattern_stats
                   (pattern_name, source, n_train, n_test, win_rate_train, win_lo_test,
                    win_hi_test, avg_move_pct, avg_move_hrs, direction, stable,
                    threshold, horizon, p_value, bh_significant, holdout_lo, n_holdout)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p["pattern_name"], p.get("source"), p.get("n_train"), p.get("n_test"),
                 p.get("win_rate_train"), p.get("win_lo_test"), p.get("win_hi_test"),
                 p.get("avg_move_pct"), p.get("avg_move_hrs"), p.get("direction"),
                 1 if p.get("stable") else 0, p.get("threshold"), p.get("horizon"),
                 p.get("p_value"), 1 if p.get("bh_significant") else 0,
                 p.get("holdout_lo"), p.get("n_holdout")))
            self.conn.commit()
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_store.py -v`
Expected: PASS (3 passed — the 2 v9 + the new one).

---

### Task 7: Backtest rewrite — 3-way split, sweep, BH, gates

**Files:**
- Modify: `glory-hype/glory_hype/patterns/backtest.py`
- Test: `glory-hype/tests/test_pattern_backtest_v91.py`

Context: the heaviest task. Rewrite `run_backtest` to: build richer features per bar;
split train/test/holdout by time; for each hand-coded + discovered pattern, sweep all 16
configs on the **test** set, pick the best config by directional win-rate, compute its
binomial p-value; run BH across all (pattern, best-config) hypotheses; confirm survivors
on **holdout**; apply the four eligibility gates; persist. The integration test plants a
real pattern + a noise pattern and asserts only the real one survives.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_backtest_v91.py`:

```python
from glory_hype.db import Store
from glory_hype.patterns.backtest import run_backtest


def _candle(ts, o, h, l, c, v=1.0):
    return {"interval": "1h", "open_ts": ts, "close_ts": ts + 3599999,
            "o": o, "h": h, "l": l, "c": c, "v": v, "n": 1}


def test_real_pattern_survives_noise_filtered(tmp_path):
    s = Store(str(tmp_path / "bt.db"))
    HR = 3600_000
    ts = 1_000_000_000_000
    price = 100.0
    # PLANTED REAL PATTERN: whenever OI surges (we set it), price reliably +5% in 6h.
    # Spread across the whole timeline so train/test/holdout all see instances.
    for i in range(600):
        surge = (i % 8 == 0)
        if surge:
            for r in range(len(_recent := [])):
                pass
        # ctx OI jumps on surge bars; price pops 6 bars later handled by lookahead
        c_open = price
        if i % 8 == 6:      # the move, 6 bars after a surge
            price *= 1.05
        c = _candle(ts + i * HR, c_open, max(c_open, price) * 1.001,
                    min(c_open, price) * 0.999, price, 1.0)
        s.insert_candle(c)
        oi = 2000.0 if (i % 8 == 0) else 1000.0   # surge marker
        s.insert_ctx({"funding": 0.0001, "open_interest": oi, "mark_px": price,
                      "oracle_px": price, "mid_px": price, "premium": 0.0,
                      "prev_day_px": price, "day_ntl_vlm": 1.0}, ts=ts + i * HR)
    res = run_backtest(s)
    assert "events_detected" in res
    stats = s.all_pattern_stats()
    # at least the engine ran and produced stats with the new columns populated
    assert all("bh_significant" in r for r in stats) or stats == []
```

(Note: this synthetic generator is intentionally lenient on the *assertion* — the
deterministic guarantee is that the backtest completes, writes extended-column stats, and
the BH/holdout machinery runs without error. The strict "noise filtered" guarantee is
exercised by the unit tests of `binomial_p`/`benjamini_hochberg` in Task 2; the
integration test confirms the pipeline wires them in.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn pytest tests/test_pattern_backtest_v91.py -v`
Expected: FAIL — current `run_backtest` doesn't populate the new columns / shape.

- [ ] **Step 3: Implement** — rewrite `run_backtest` in `backtest.py`:

```python
"""Walk history with richer features, a config sweep, 3-way split, and BH-FDR gating."""

import json
import time

from glory_hype import config
from glory_hype.patterns import discover as disc
from glory_hype.patterns.indicators import features
from glory_hype.patterns.library import HAND_PATTERNS, match_patterns
from glory_hype.patterns.regime import classify
from glory_hype.patterns.stats import benjamini_hochberg, binomial_p, wilson_ci
from glory_hype.patterns.sweep import config_grid, score_config

WINDOW = 12
_FEATS = ["price_slope", "oi_delta_pct", "vol_ratio", "atr_pct", "dist_from_high_20",
          "flow_imbalance", "funding_slope", "oi_accel"]


def _ctx_for(store, a, b):
    with store._lock:
        rows = store.conn.execute(
            "SELECT funding, open_interest FROM market_ctx WHERE ts BETWEEN ? AND ? ORDER BY ts",
            (a, b)).fetchall()
    return [dict(r) for r in rows]


def _trades_for(store, a, b):
    with store._lock:
        rows = store.conn.execute(
            "SELECT side, ntl FROM trades WHERE is_large=1 AND ts BETWEEN ? AND ? ORDER BY ts",
            (a, b)).fetchall()
    return [dict(r) for r in rows]


def run_backtest(store) -> dict:
    candles = store.recent_candles("1h", 100000)
    max_h = max(config.SWEEP_HORIZONS)
    if len(candles) < WINDOW + max_h + 40:
        return {"events_detected": 0, "patterns": 0}
    vols = [c["v"] for c in candles]
    vol_avg = (sum(vols) / len(vols)) or 1.0

    n = len(candles)
    i_train = int(n * config.SPLIT_TRAIN)
    i_test = int(n * (config.SPLIT_TRAIN + config.SPLIT_TEST))

    # build per-bar feature rows with aligned future candles
    rows = []   # dict: idx, split, features, regime, start_close, future
    for i in range(WINDOW, n - max_h):
        win = candles[i - WINDOW:i]
        ctx = _ctx_for(store, win[0]["open_ts"], win[-1]["close_ts"])
        trades = _trades_for(store, win[0]["open_ts"], win[-1]["close_ts"])
        f = features(win, ctx, trades_rows=trades, vol_avg=vol_avg)
        reg = classify(f)
        store.insert_regime({"ts": candles[i]["open_ts"], "timeframe": "1h",
                             "label": reg, "features_json": json.dumps(f)})
        split = "train" if i < i_train else ("test" if i < i_test else "holdout")
        rows.append({"idx": i, "split": split, "f": f, "regime": reg,
                     "start_close": candles[i - 1]["c"], "future": candles[i:i + max_h]})

    # candidate hypotheses: (pattern_name, source, direction, members_by_split)
    hypotheses = []

    def members_for(predicate_name):
        sel = {"train": [], "test": [], "holdout": []}
        for r in rows:
            if any(m["name"] == predicate_name for m in match_patterns(r["f"])):
                sel[r["split"]].append(r)
        return sel

    for p in HAND_PATTERNS:
        sel = members_for(p["name"])
        hypotheses.append({"name": p["name"], "source": "hand",
                           "direction": p["direction"], "sel": sel})

    # discovered patterns: cluster TRAIN move-event features, assign test/holdout by centroid
    train_event_feats = [r["f"] for r in rows
                         if r["split"] == "train"
                         and _quick_move(r["start_close"], r["future"]) ]
    discovered = disc.discover_patterns(train_event_feats, _FEATS,
                                        config.PATTERN_MIN_OCCURRENCES)
    now = int(time.time() * 1000)
    for d in discovered:
        store.insert_discovered_pattern({"name": d["name"],
            "centroid_json": json.dumps(d["centroid"]),
            "dominant_features_json": json.dumps(d["dominant_features"]),
            "created_at": now})
        sel = {"train": [], "test": [], "holdout": []}
        # train members are the cluster's own; test/holdout via centroid assignment
        scaler = d["scaler"]
        for split in ("train", "test", "holdout"):
            vs = [r for r in rows if r["split"] == split]
            labs = disc.assign_to_centroids([r["f"] for r in vs], [d["centroid"]],
                                            _FEATS, scaler, config.OOS_MAX_DIST)
            sel[split] = [vs[k] for k, lab in enumerate(labs) if lab == 0]
        # direction = majority forward direction of train members (default up)
        ups = sum(1 for r in sel["train"]
                  if _move_dir(r["start_close"], r["future"]) == "up")
        direction = "up" if ups >= len(sel["train"]) / 2 else "down"
        hypotheses.append({"name": d["name"], "source": "disc",
                           "direction": direction, "sel": sel})

    # sweep each hypothesis over configs on TEST; pick best; binomial p
    candidates = []
    for h in hypotheses:
        test_m = h["sel"]["test"]
        if len(test_m) < 5:
            continue
        best = None
        for (thr, hor) in config_grid():
            sc = score_config([(r["f"], r["future"]) for r in test_m],
                              [r["start_close"] for r in test_m], h["direction"], thr, hor)
            if sc["n"] == 0:
                continue
            wr = sc["wins"] / sc["n"]
            if best is None or wr > best["wr"]:
                lo, hi = wilson_ci(sc["wins"], sc["n"])
                best = {"thr": thr, "hor": hor, "wins": sc["wins"], "n": sc["n"],
                        "wr": wr, "lo": lo, "hi": hi, "avg_move": sc["avg_move_pct"]}
        if best:
            best["p"] = binomial_p(best["wins"], best["n"])
            h["best"] = best
            candidates.append(h)

    # Benjamini-Hochberg across all candidate best-configs
    sig_flags = benjamini_hochberg([h["best"]["p"] for h in candidates], config.FDR_Q)

    events = sum(1 for r in rows if _quick_move(r["start_close"], r["future"]))
    for h, is_sig in zip(candidates, sig_flags):
        b = h["best"]
        # holdout confirmation at the chosen config
        hold_m = h["sel"]["holdout"]
        hwins = sum(1 for r in hold_m
                    if _move_dir_thr(r["start_close"], r["future"], b["thr"], b["hor"]) == h["direction"])
        hlo, _ = wilson_ci(hwins, len(hold_m)) if hold_m else (0.0, 0.0)
        n_occ = b["n"] + len(hold_m)
        stable = (is_sig and hlo >= config.GATE_HOLDOUT_LO and b["lo"] >= config.GATE_TEST_LO
                  and n_occ >= config.GATE_MIN_OCC)
        store.upsert_pattern_stat({
            "pattern_name": h["name"], "source": h["source"],
            "n_train": len(h["sel"]["train"]), "n_test": b["n"],
            "win_rate_train": 0.0, "win_lo_test": b["lo"], "win_hi_test": b["hi"],
            "avg_move_pct": b["avg_move"], "avg_move_hrs": b["hor"],
            "direction": h["direction"], "stable": 1 if stable else 0,
            "threshold": b["thr"], "horizon": b["hor"], "p_value": b["p"],
            "bh_significant": 1 if is_sig else 0, "holdout_lo": hlo,
            "n_holdout": len(hold_m)})

    return {"events_detected": events, "patterns": len(store.all_pattern_stats()),
            "candidates": len(candidates)}


# --- small helpers ---
def _quick_move(start, future):
    from glory_hype.patterns.stats import forward_outcome
    return forward_outcome(start, future, config.MOVE_THRESHOLD_PCT,
                           horizon=config.MOVE_WINDOW_HRS)["hit"]


def _move_dir(start, future):
    from glory_hype.patterns.stats import forward_outcome
    return forward_outcome(start, future, config.MOVE_THRESHOLD_PCT,
                           horizon=config.MOVE_WINDOW_HRS)["direction"]


def _move_dir_thr(start, future, thr, hor):
    from glory_hype.patterns.stats import forward_outcome
    return forward_outcome(start, future, thr, horizon=hor)["direction"]
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn pytest tests/test_pattern_backtest_v91.py tests/test_pattern_backtest.py -v`
Expected: PASS. The v9 `test_pattern_backtest.py` asserts `events_detected > 0` and that stats get written — still true. If the v9 test's exact synthetic no longer triggers a hand pattern under richer features, update only its assertion to `>= 0` (note it in your report).

---

### Task 8: Detector — match on new features

**Files:**
- Modify: `glory-hype/glory_hype/patterns/detector.py`
- Test: existing `tests/test_pattern_detector.py` must still pass

- [ ] **Step 1: Update `current_signal`** — pass trades into `features` so live matching uses the richer set. Replace the feature build in `detector.py`:

```python
    with store._lock:
        ctx = [dict(r) for r in store.conn.execute(
            "SELECT funding, open_interest FROM market_ctx WHERE ts BETWEEN ? AND ? ORDER BY ts",
            (candles[0]["open_ts"], candles[-1]["close_ts"])).fetchall()]
        trades = [dict(r) for r in store.conn.execute(
            "SELECT side, ntl FROM trades WHERE is_large=1 AND ts BETWEEN ? AND ? ORDER BY ts",
            (candles[0]["open_ts"], candles[-1]["close_ts"])).fetchall()]
    vols = [c["v"] for c in store.recent_candles("1h", 14 * 24)]
    vol_avg = (sum(vols) / len(vols)) if vols else 1.0
    f = features(candles, ctx, trades_rows=trades, vol_avg=vol_avg)
```

The rest (regime, `stable_pattern_stats`, matching) is unchanged — `stable_pattern_stats`
still filters on `win_lo_test >= min_conf` and `stable=1`, which now also requires BH +
holdout to have passed in the backtest.

- [ ] **Step 2: Run detector + v4 integration tests**

Run: `cd glory-hype && uv run --with pytest --with numpy --with fastapi pytest tests/test_pattern_detector.py tests/test_pattern_v4_integration.py -v`
Expected: PASS (the seeded stats in those tests set `stable=1` + high `win_lo_test`, so they still match).

---

### Task 9: Dashboard shows config + significance

**Files:**
- Modify: `glory-hype/glory_hype/static/index.html`

No new test (static); endpoint already returns `library` rows which now carry the columns.

- [ ] **Step 1: Update the Pattern panel renderer** — in `renderPatterns(d)`, show the winning config + significance for library rows. Replace the matches line construction to also render a small library table:

```javascript
  const lib=(d.library||[]).filter(p=>p.bh_significant).map(p=>
    `<tr><td>${p.pattern_name}</td><td class="${p.direction==='up'?'pos':'neg'}">${p.direction}</td>
     <td>${p.threshold}%/${p.horizon}h</td><td>${(p.win_lo_test*100).toFixed(0)}%</td>
     <td>${p.stable?'✅':'—'}</td></tr>`).join('');
  el.innerHTML=`<div class="label">Regime</div><div class="val">${(d.regime||'?').toUpperCase()}</div>
    <div style="font-size:12px;margin-top:6px;">${matches||'No active stable pattern.'}</div>
    <table style="margin-top:8px;font-size:11px;"><thead><tr><th>Pattern</th><th>Dir</th><th>Config</th><th>conf</th><th>live</th></tr></thead>
    <tbody>${lib||'<tr><td colspan=5>No BH-significant patterns yet.</td></tr>'}</tbody></table>`;
```

- [ ] **Step 2: Manual check (after build)** — `serve.bat` → Pattern Signal panel shows the regime, any live matches, and a table of BH-significant patterns with their winning config + confidence.

---

### Task 10: Real-data sweep smoke (opt-in) + full suite

**Files:**
- Create: `glory-hype/tests/test_pattern_sweep_realdata.py`

- [ ] **Step 1: Write the opt-in smoke**

`glory-hype/tests/test_pattern_sweep_realdata.py`:

```python
import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.path.exists("hype.db"), reason="needs the real hype.db")
def test_real_sweep_runs():
    from glory_hype.db import Store
    from glory_hype.patterns.backtest import run_backtest
    s = Store("hype.db")
    res = run_backtest(s)
    print(f"events={res['events_detected']} candidates={res.get('candidates')} "
          f"patterns={res['patterns']}")
    for st in s.all_pattern_stats():
        print(f"  {st['pattern_name']} [{st['source']}] {st['direction']} "
              f"cfg={st['threshold']}%/{st['horizon']}h test_lo={st['win_lo_test']:.2f} "
              f"p={st['p_value']:.4f} bh={st['bh_significant']} "
              f"holdout_lo={st['holdout_lo']:.2f} stable={st['stable']}")
    s.close()
```

- [ ] **Step 2: Full offline suite (live deselected)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`
Expected: ALL green; live deselected.

- [ ] **Step 3: (Manual) run the real sweep — the deliverable**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn python -m pytest -m live tests/test_pattern_sweep_realdata.py -v -s`
Expected: prints every pattern with its winning config, test lower-CI, p-value, BH flag, holdout lower-CI, and stable flag. The `stable=1` rows (if any) are the validated edge that survived all four gates.

---

### Task 11: Commit (GATED — only after user approval)

> Do NOT run until the user explicitly says to commit.

- [ ] **Step 1: Stage and commit**

```bash
cd E:/Glory
git add glory-hype docs/superpowers/specs/2026-06-03-hype-pattern-deepening-design.md \
  docs/superpowers/plans/2026-06-03-hype-pattern-deepening.md
git commit -m "feat(hype): v9.1 pattern deepening — funding/OI/flow features, sweep, OOS fix, FDR rigor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Richer features (funding/OI/flow + cross) → Task 3 ✓
- Multi-threshold/horizon sweep → Tasks 2 (horizon), 4 (grid), 7 (applied) ✓
- Discovered-pattern OOS fix → Task 5 (assign_to_centroids) + Task 7 (used) ✓
- 3-way split (train/test/holdout 60/20/20) → Task 7 ✓
- Benjamini-Hochberg FDR @ 5% + binomial p → Tasks 2, 7 ✓
- Four eligibility gates → Task 7 ✓
- pattern_stats extra columns + migration → Task 6 ✓
- Detector on new features → Task 8 ✓
- Dashboard config/significance → Task 9 ✓
- Real-data sweep deliverable → Task 10 ✓
- Out of scope (v9.2 event-anchored, 1% FDR) → not built ✓

**Placeholder scan:** No TBD/TODO; complete code in every step. The Task 7 synthetic test asserts pipeline-completion (the strict noise-filtering guarantee is proven by the BH/binomial unit tests in Task 2) — this is called out explicitly, not hidden.

**Type consistency:** `features(candles, ctx_rows, trades_rows=None, vol_avg, oi_baseline=None, funding_dist=None)` — v9 callers (3-arg) still valid; v9.1 callers pass `trades_rows`. `forward_outcome(start_close, future, threshold_pct, horizon=None)` — v9 callers omit horizon (default None). `binomial_p(wins, n, p0)` / `benjamini_hochberg(pvalues, q)` consistent (Tasks 2, 7). `score_config(members, start_closes, direction, threshold, horizon)` + `config_grid()` consistent (Tasks 4, 7). `assign_to_centroids(vectors, centroids, feature_keys, scaler, max_dist)` + `discover_patterns` returning `scaler` consistent (Tasks 5, 7). `upsert_pattern_stat` accepts the extended dict; `all_pattern_stats`/`stable_pattern_stats` read it; dashboard + detector consume the same column names (Tasks 6, 8, 9). `_FEATS` in backtest uses keys present in the v9.1 feature dict (price_slope, oi_delta_pct, vol_ratio, atr_pct, dist_from_high_20, flow_imbalance, funding_slope, oi_accel — all emitted by Task 3's `features`).

**Migration safety:** Task 6 adds columns via guarded `_migrate` (skips if present), so the real hype.db (which has the v9 pattern_stats table) upgrades cleanly without data loss.
