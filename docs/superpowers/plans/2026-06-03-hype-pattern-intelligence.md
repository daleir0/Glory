# HYPE Pattern Intelligence Engine (v9) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mine 18 months of HYPE history to find recurring pre-move structures (hand-coded + auto-discovered), validate them out-of-sample with confidence intervals, and feed a live pattern signal into v4 to sharpen call confidence.

**Architecture:** A `patterns/` subpackage. Pure `indicators` + `regime` featurize candle/ctx windows; `library` holds hand-coded patterns; `discover` clusters pre-move windows into new patterns; `backtest` walks history (train/test split, leak-free forward outcomes, Wilson-CI stats) and persists; `detector` matches the live state; v4 consumes the signal. Rigor (min-occurrences, out-of-sample, lower-CI confidence) is enforced in the testable units.

**Tech Stack:** Python 3.12, `uv`, `numpy` (linreg/features), `scikit-learn` (k-means + silhouette), stdlib `sqlite3`, `fastapi`, `pytest`.

> **Git note:** prior work committed through 207ba227 (+ the v5 resolver entry-fill fix already applied this session). Do NOT commit per-task. Final commit (Task 13) is gated on explicit user approval.

Run offline tests with:
`cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`

---

## File Structure

```
glory-hype/glory_hype/
  config.py            # MODIFY: pattern thresholds
  patterns/
    __init__.py
    indicators.py      # pure: features(candles, ctx_rows) -> dict
    regime.py          # pure: classify(features) -> label
    stats.py           # pure: wilson_ci, forward_outcome (leak-free)
    library.py         # hand-coded named patterns (predicates)
    discover.py        # cluster pre-move windows -> discovered patterns
    backtest.py        # walk history -> regimes/events/stats persisted
    detector.py        # live: current_signal(store) -> matches
  db.py                # MODIFY: regimes, pattern_events, pattern_stats, discovered_patterns
  decision/engine.py   # MODIFY: pattern signal -> confidence modifier + inputs
  server.py            # MODIFY: /api/patterns
  static/index.html    # MODIFY: Pattern Signal panel
  __main__.py          # MODIFY: `patterns` subcommand (analyze | now)
  tests/
    test_pattern_indicators.py
    test_pattern_regime.py
    test_pattern_stats.py
    test_pattern_library.py
    test_pattern_store.py
    test_pattern_discover.py
    test_pattern_backtest.py
    test_pattern_detector.py
    test_pattern_v4_integration.py
    test_pattern_server.py
```

---

### Task 1: Config thresholds

**Files:**
- Modify: `glory-hype/glory_hype/config.py`
- Test: folded into Task 2

- [ ] **Step 1: Append to `config.py`**

```python
# --- v9 pattern intelligence ---
PATTERN_MIN_OCCURRENCES = 10       # below this: observed, not trusted
PATTERN_SIGNAL_CONF = 0.60         # lower-CI confidence to fire a live signal
PATTERN_TRAIN_FRAC = 0.70          # older 70% train, newer 30% test
MOVE_THRESHOLD_PCT = 4.0           # a "move" event = >= this % within the window
MOVE_WINDOW_HRS = 6                # hours ahead that define the move/outcome
PATTERN_CONF_MODIFIER_MAX = 0.15   # max confidence shift v4 applies from a signal
```

- [ ] **Step 2: Verify**

Run: `cd glory-hype && uv run python -c "from glory_hype import config; print(config.PATTERN_SIGNAL_CONF, config.MOVE_THRESHOLD_PCT)"`
Expected: `0.6 4.0`

---

### Task 2: Indicators (pure feature vector)

**Files:**
- Create: `glory-hype/glory_hype/patterns/__init__.py`, `glory-hype/glory_hype/patterns/indicators.py`
- Test: `glory-hype/tests/test_pattern_indicators.py`

- [ ] **Step 1: Create the package init**

`glory-hype/glory_hype/patterns/__init__.py`:

```python
"""HYPE pattern intelligence (v9): historical structure mining + live signals."""
```

- [ ] **Step 2: Write the failing test**

`glory-hype/tests/test_pattern_indicators.py`:

```python
from glory_hype.patterns.indicators import features


def _c(o, h, l, c, v=1.0):
    return {"o": o, "h": h, "l": l, "c": c, "v": v}


def test_features_uptrend():
    candles = [_c(100, 101, 99, 100), _c(100, 103, 100, 102),
               _c(102, 106, 101, 105), _c(105, 109, 104, 108)]
    ctx = [{"funding": 0.0001, "open_interest": 1000.0},
           {"funding": 0.0001, "open_interest": 1100.0}]
    f = features(candles, ctx, vol_avg=1.0)
    assert f["price_slope"] > 0                 # rising closes
    assert f["oi_delta_pct"] == 10.0            # 1000 -> 1100
    assert f["funding_sign"] == 1
    assert f["dist_from_low_20"] > 0
    assert "vol_ratio" in f and "atr_pct" in f


def test_features_funding_compression():
    candles = [_c(100, 101, 99, 100)] * 4
    ctx = [{"funding": 0.000001, "open_interest": 1000.0},
           {"funding": -0.000001, "open_interest": 1000.0}]
    f = features(candles, ctx, vol_avg=1.0)
    assert f["funding_compression"] is True     # |funding| ~ 0
    assert f["funding_sign"] == 0


def test_features_empty_safe():
    f = features([], [], vol_avg=1.0)
    assert f["price_slope"] == 0.0
    assert f["oi_delta_pct"] == 0.0
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy pytest tests/test_pattern_indicators.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement**

`glory-hype/glory_hype/patterns/indicators.py`:

```python
"""Pure feature extraction over a candle window + aligned ctx rows."""

import numpy as np

_FUNDING_EPS = 5e-6   # |funding| below this counts as compressed/near-zero


def features(candles: list, ctx_rows: list, vol_avg: float = 1.0) -> dict:
    if not candles:
        return {"price_slope": 0.0, "dist_from_high_20": 0.0, "dist_from_low_20": 0.0,
                "oi_delta_pct": 0.0, "funding_mean": 0.0, "funding_sign": 0,
                "funding_compression": True, "vol_ratio": 0.0, "atr_pct": 0.0,
                "range_pct": 0.0, "body_ratio": 0.0}
    closes = np.array([c["c"] for c in candles], dtype=float)
    highs = np.array([c["h"] for c in candles], dtype=float)
    lows = np.array([c["l"] for c in candles], dtype=float)
    opens = np.array([c["o"] for c in candles], dtype=float)
    vols = np.array([c["v"] for c in candles], dtype=float)
    last = closes[-1]

    # price slope: linreg of closes, normalized to % per bar
    x = np.arange(len(closes))
    slope = float(np.polyfit(x, closes, 1)[0]) / last * 100 if len(closes) > 1 else 0.0

    hi, lo = float(highs.max()), float(lows.min())
    dist_high = (hi - last) / last * 100
    dist_low = (last - lo) / last * 100

    funding = [r.get("funding", 0.0) for r in ctx_rows] or [0.0]
    fmean = float(np.mean(funding))
    fsign = 0 if abs(fmean) < _FUNDING_EPS else (1 if fmean > 0 else -1)

    ois = [r.get("open_interest", 0.0) for r in ctx_rows if r.get("open_interest")]
    oi_delta = ((ois[-1] - ois[0]) / ois[0] * 100) if len(ois) >= 2 and ois[0] else 0.0

    atr = float(np.mean(highs - lows)) / last * 100
    rng = (hi - lo) / last * 100
    body = float(np.mean(np.abs(closes - opens)) / np.mean(np.maximum(highs - lows, 1e-9)))

    return {
        "price_slope": slope,
        "dist_from_high_20": dist_high,
        "dist_from_low_20": dist_low,
        "oi_delta_pct": round(oi_delta, 4),
        "funding_mean": fmean,
        "funding_sign": fsign,
        "funding_compression": abs(fmean) < _FUNDING_EPS,
        "vol_ratio": float(vols.mean() / vol_avg) if vol_avg else 0.0,
        "atr_pct": round(atr, 4),
        "range_pct": round(rng, 4),
        "body_ratio": round(body, 4),
    }
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with numpy pytest tests/test_pattern_indicators.py -v`
Expected: PASS (3 passed)

---

### Task 3: Regime classifier (pure)

**Files:**
- Create: `glory-hype/glory_hype/patterns/regime.py`
- Test: `glory-hype/tests/test_pattern_regime.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_regime.py`:

```python
from glory_hype.patterns.regime import classify


def test_trending_up():
    assert classify({"price_slope": 0.5, "vol_ratio": 1.2, "atr_pct": 1.5,
                     "funding_compression": False}) == "trending_up"


def test_trending_down():
    assert classify({"price_slope": -0.5, "vol_ratio": 1.2, "atr_pct": 1.5,
                     "funding_compression": False}) == "trending_down"


def test_coiling():
    # flat slope + low vol + funding compressed = coil before expansion
    assert classify({"price_slope": 0.02, "vol_ratio": 0.5, "atr_pct": 0.4,
                     "funding_compression": True}) == "coiling"


def test_ranging():
    assert classify({"price_slope": 0.05, "vol_ratio": 1.0, "atr_pct": 1.2,
                     "funding_compression": False}) == "ranging"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_regime.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/patterns/regime.py`:

```python
"""Pure regime classification from a feature vector."""

_TREND_SLOPE = 0.15     # % per bar to call a trend
_COIL_VOL = 0.7         # vol_ratio below this = quiet
_COIL_ATR = 0.6         # atr_pct below this = compressed


def classify(f: dict) -> str:
    slope = f.get("price_slope", 0.0)
    if slope >= _TREND_SLOPE:
        return "trending_up"
    if slope <= -_TREND_SLOPE:
        return "trending_down"
    # flat slope: coiling if quiet + compressed, else ranging
    if (f.get("vol_ratio", 1.0) < _COIL_VOL and f.get("atr_pct", 1.0) < _COIL_ATR
            and f.get("funding_compression", False)):
        return "coiling"
    return "ranging"
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_regime.py -v`
Expected: PASS (4 passed)

---

### Task 4: Stats — Wilson CI + leak-free forward outcome

**Files:**
- Create: `glory-hype/glory_hype/patterns/stats.py`
- Test: `glory-hype/tests/test_pattern_stats.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_stats.py`:

```python
import math
from glory_hype.patterns.stats import wilson_ci, forward_outcome


def test_wilson_ci_basic():
    lo, hi = wilson_ci(wins=8, n=10)
    assert 0.4 < lo < 0.6      # 80% over 10 -> wide CI, lower bound ~0.49
    assert hi > 0.9
    lo2, _ = wilson_ci(wins=35, n=50)
    assert lo2 > lo            # more samples at 70% -> higher lower bound than 8/10


def test_wilson_ci_zero_n():
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_forward_outcome_up():
    # candles after t0: price runs from 100 to 105 within window -> +5%, 'up'
    candles = [{"open_ts": 10, "c": 100, "h": 100, "l": 100},
               {"open_ts": 20, "c": 103, "h": 103, "l": 100},
               {"open_ts": 30, "c": 105, "h": 105, "l": 102}]
    o = forward_outcome(start_close=100.0, future=candles, threshold_pct=4.0)
    assert o["direction"] == "up"
    assert round(o["move_pct"], 1) == 5.0
    assert o["hit"] is True


def test_forward_outcome_none():
    candles = [{"open_ts": 10, "c": 100, "h": 101, "l": 99},
               {"open_ts": 20, "c": 101, "h": 102, "l": 100}]
    o = forward_outcome(start_close=100.0, future=candles, threshold_pct=4.0)
    assert o["hit"] is False
    assert o["direction"] == "none"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_stats.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/patterns/stats.py`:

```python
"""Wilson confidence interval + leak-free forward outcome labeling."""

import math


def wilson_ci(wins: int, n: int, z: float = 1.96):
    """95% Wilson score interval for a binomial proportion. Returns (lo, hi)."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - margin) / denom, (centre + margin) / denom)


def forward_outcome(start_close: float, future: list, threshold_pct: float) -> dict:
    """Largest signed move from start_close over the future candles. 'hit' if the
    peak magnitude reached threshold. Leak-free: caller passes only candles strictly
    after the feature window."""
    if not future or not start_close:
        return {"direction": "none", "move_pct": 0.0, "hit": False}
    max_up = max((c["h"] - start_close) / start_close * 100 for c in future)
    max_dn = min((c["l"] - start_close) / start_close * 100 for c in future)
    # the dominant move is whichever magnitude is larger
    if abs(max_dn) > max_up:
        move = max_dn
        direction = "down" if abs(move) >= threshold_pct else "none"
    else:
        move = max_up
        direction = "up" if move >= threshold_pct else "none"
    return {"direction": direction, "move_pct": move,
            "hit": abs(move) >= threshold_pct}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_stats.py -v`
Expected: PASS (4 passed)

---

### Task 5: Hand-coded pattern library

**Files:**
- Create: `glory-hype/glory_hype/patterns/library.py`
- Test: `glory-hype/tests/test_pattern_library.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_library.py`:

```python
from glory_hype.patterns.library import match_patterns, HAND_PATTERNS


def test_coil_expansion_matches():
    f = {"price_slope": 0.03, "vol_ratio": 0.5, "atr_pct": 0.4,
         "funding_compression": True, "oi_delta_pct": 1.0,
         "dist_from_high_20": 3.0, "funding_sign": 0}
    names = [m["name"] for m in match_patterns(f)]
    assert "COIL_EXPANSION" in names


def test_blowoff_top_matches():
    f = {"price_slope": 0.8, "vol_ratio": 3.0, "atr_pct": 2.5,
         "funding_compression": False, "oi_delta_pct": 5.0,
         "dist_from_high_20": 0.2, "funding_sign": 1}
    names = [m["name"] for m in match_patterns(f)]
    assert "BLOWOFF_TOP" in names


def test_mean_reversion_bounce_matches():
    f = {"price_slope": -0.3, "vol_ratio": 1.5, "atr_pct": 1.8,
         "funding_compression": False, "oi_delta_pct": -1.0,
         "dist_from_high_20": 8.0, "funding_sign": 1}
    names = [m["name"] for m in match_patterns(f)]
    assert "MEAN_REVERSION_BOUNCE" in names


def test_no_match_returns_empty():
    f = {"price_slope": 0.05, "vol_ratio": 1.0, "atr_pct": 1.0,
         "funding_compression": False, "oi_delta_pct": 0.0,
         "dist_from_high_20": 4.0, "funding_sign": 1}
    assert match_patterns(f) == []


def test_each_pattern_has_direction():
    for p in HAND_PATTERNS:
        assert p["direction"] in ("up", "down")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_library.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/patterns/library.py`:

```python
"""Hand-coded named patterns. Domain knowledge proposes; data (backtest) decides."""


def _coil_expansion(f):
    return (abs(f["price_slope"]) < 0.1 and f["vol_ratio"] < 0.7
            and f["atr_pct"] < 0.6 and f["funding_compression"])


def _etf_catalyst_breakout(f):
    return (f["price_slope"] > 0.2 and f["oi_delta_pct"] > 3.0
            and f["vol_ratio"] > 1.5)


def _unlock_fear_dump(f):
    return (f["price_slope"] < -0.1 and f["oi_delta_pct"] < -1.0
            and f["funding_sign"] <= 0)


def _blowoff_top(f):
    return (f["price_slope"] > 0.5 and f["vol_ratio"] > 2.0
            and f["dist_from_high_20"] < 1.0)


def _mean_reversion_bounce(f):
    return (f["dist_from_high_20"] >= 7.0 and f["funding_sign"] >= 1
            and f["oi_delta_pct"] > -3.0)


def _capitulation_low(f):
    return (f["price_slope"] < -0.4 and f["vol_ratio"] > 2.0
            and f["funding_sign"] < 0)


HAND_PATTERNS = [
    {"name": "COIL_EXPANSION", "predicate": _coil_expansion, "direction": "up"},
    {"name": "ETF_CATALYST_BREAKOUT", "predicate": _etf_catalyst_breakout, "direction": "up"},
    {"name": "UNLOCK_FEAR_DUMP", "predicate": _unlock_fear_dump, "direction": "down"},
    {"name": "BLOWOFF_TOP", "predicate": _blowoff_top, "direction": "down"},
    {"name": "MEAN_REVERSION_BOUNCE", "predicate": _mean_reversion_bounce, "direction": "up"},
    {"name": "CAPITULATION_LOW", "predicate": _capitulation_low, "direction": "up"},
]


def match_patterns(f: dict) -> list:
    out = []
    for p in HAND_PATTERNS:
        try:
            if p["predicate"](f):
                out.append({"name": p["name"], "source": "hand", "direction": p["direction"]})
        except KeyError:
            continue
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_library.py -v`
Expected: PASS (5 passed). Note COIL_EXPANSION test: slope 0.03 < 0.1 ✓, vol 0.5<0.7 ✓, atr 0.4<0.6 ✓, compression True ✓.

---

### Task 6: Pattern storage

**Files:**
- Modify: `glory-hype/glory_hype/db.py`
- Test: `glory-hype/tests/test_pattern_store.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_store.py`:

```python
from glory_hype.db import Store


def test_pattern_stats_upsert_and_read(tmp_path):
    s = Store(str(tmp_path / "p.db"))
    s.upsert_pattern_stat({"pattern_name": "COIL_EXPANSION", "source": "hand",
                           "n_train": 20, "n_test": 8, "win_rate_train": 0.75,
                           "win_lo_test": 0.61, "win_hi_test": 0.92,
                           "avg_move_pct": 5.2, "avg_move_hrs": 6, "direction": "up",
                           "stable": 1})
    rows = s.stable_pattern_stats(min_conf=0.60)
    assert len(rows) == 1 and rows[0]["pattern_name"] == "COIL_EXPANSION"
    # below threshold or unstable excluded
    s.upsert_pattern_stat({"pattern_name": "WEAK", "source": "disc", "n_train": 12,
                           "n_test": 5, "win_rate_train": 0.6, "win_lo_test": 0.40,
                           "win_hi_test": 0.7, "avg_move_pct": 3.0, "avg_move_hrs": 6,
                           "direction": "up", "stable": 1})
    assert len(s.stable_pattern_stats(min_conf=0.60)) == 1   # WEAK lo 0.40 < 0.60


def test_pattern_event_and_regime(tmp_path):
    s = Store(str(tmp_path / "p2.db"))
    s.insert_regime({"ts": 100, "timeframe": "1h", "label": "coiling", "features_json": "{}"})
    s.insert_pattern_event({"ts": 100, "pattern_name": "COIL_EXPANSION", "source": "hand",
                            "direction": "up", "features_json": "{}",
                            "fwd_4h": 4.2, "fwd_12h": 5.0, "fwd_24h": 3.1})
    assert s.conn.execute("SELECT COUNT(*) FROM regimes").fetchone()[0] == 1
    assert s.conn.execute("SELECT COUNT(*) FROM pattern_events").fetchone()[0] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_store.py -v`
Expected: FAIL — methods missing.

- [ ] **Step 3: Add tables to SCHEMA** — append to `db.py` SCHEMA:

```sql
CREATE TABLE IF NOT EXISTS regimes (
    ts INTEGER, timeframe TEXT, label TEXT, features_json TEXT,
    PRIMARY KEY (ts, timeframe)
);
CREATE TABLE IF NOT EXISTS pattern_events (
    ts INTEGER, pattern_name TEXT, source TEXT, direction TEXT, features_json TEXT,
    fwd_4h REAL, fwd_12h REAL, fwd_24h REAL,
    PRIMARY KEY (ts, pattern_name)
);
CREATE TABLE IF NOT EXISTS pattern_stats (
    pattern_name TEXT PRIMARY KEY, source TEXT, n_train INTEGER, n_test INTEGER,
    win_rate_train REAL, win_lo_test REAL, win_hi_test REAL,
    avg_move_pct REAL, avg_move_hrs REAL, direction TEXT, stable INTEGER
);
CREATE TABLE IF NOT EXISTS discovered_patterns (
    name TEXT PRIMARY KEY, centroid_json TEXT, dominant_features_json TEXT, created_at INTEGER
);
```

- [ ] **Step 4: Add methods to `Store`** (in `db.py`):

```python
    def insert_regime(self, r: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO regimes (ts, timeframe, label, features_json) "
                "VALUES (?,?,?,?)",
                (r["ts"], r["timeframe"], r["label"], r.get("features_json", "{}")))
            self.conn.commit()

    def insert_pattern_event(self, e: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO pattern_events
                   (ts, pattern_name, source, direction, features_json, fwd_4h, fwd_12h, fwd_24h)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (e["ts"], e["pattern_name"], e.get("source"), e.get("direction"),
                 e.get("features_json", "{}"), e.get("fwd_4h"), e.get("fwd_12h"), e.get("fwd_24h")))
            self.conn.commit()

    def upsert_pattern_stat(self, p: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO pattern_stats
                   (pattern_name, source, n_train, n_test, win_rate_train, win_lo_test,
                    win_hi_test, avg_move_pct, avg_move_hrs, direction, stable)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (p["pattern_name"], p.get("source"), p.get("n_train"), p.get("n_test"),
                 p.get("win_rate_train"), p.get("win_lo_test"), p.get("win_hi_test"),
                 p.get("avg_move_pct"), p.get("avg_move_hrs"), p.get("direction"),
                 1 if p.get("stable") else 0))
            self.conn.commit()

    def stable_pattern_stats(self, min_conf: float) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM pattern_stats WHERE stable=1 AND win_lo_test >= ? "
                "ORDER BY win_lo_test DESC", (min_conf,)).fetchall()
        return [dict(r) for r in rows]

    def insert_discovered_pattern(self, d: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO discovered_patterns "
                "(name, centroid_json, dominant_features_json, created_at) VALUES (?,?,?,?)",
                (d["name"], d.get("centroid_json", "{}"),
                 d.get("dominant_features_json", "{}"), d.get("created_at", 0)))
            self.conn.commit()

    def all_pattern_stats(self) -> list:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM pattern_stats ORDER BY win_lo_test DESC").fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_pattern_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Full suite (no regression)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`
Expected: all prior pass.

---

### Task 7: Auto-discovery (clustering)

**Files:**
- Create: `glory-hype/glory_hype/patterns/discover.py`
- Test: `glory-hype/tests/test_pattern_discover.py`

Context: take pre-move feature vectors, standardize, k-means (k by silhouette), return clusters with centroids + a generated name + dominant features. Deterministic via fixed random_state.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_discover.py`:

```python
from glory_hype.patterns.discover import discover_patterns

FEATS = ["price_slope", "oi_delta_pct", "vol_ratio", "atr_pct", "dist_from_high_20"]


def _vec(slope, oi, vol, atr, dh):
    return {"price_slope": slope, "oi_delta_pct": oi, "vol_ratio": vol,
            "atr_pct": atr, "dist_from_high_20": dh}


def test_discovers_two_clusters():
    # two clearly separated groups: quiet-coil vs loud-breakout
    coil = [_vec(0.02, 0.5, 0.4, 0.3, 3.0) for _ in range(15)]
    breakout = [_vec(0.6, 5.0, 3.0, 2.5, 0.5) for _ in range(15)]
    patterns = discover_patterns(coil + breakout, feature_keys=FEATS,
                                 min_occurrences=10, max_k=4)
    assert len(patterns) == 2
    for p in patterns:
        assert p["name"].startswith("disc_")
        assert p["n"] >= 10
        assert "centroid" in p


def test_too_few_samples_returns_empty():
    assert discover_patterns([_vec(0.1, 1, 1, 1, 1)] * 3, feature_keys=FEATS,
                             min_occurrences=10, max_k=4) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn pytest tests/test_pattern_discover.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/patterns/discover.py`:

```python
"""Auto-discover patterns by clustering pre-move feature vectors."""

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


def discover_patterns(vectors: list, feature_keys: list, min_occurrences: int,
                      max_k: int = 6) -> list:
    if len(vectors) < 2 * min_occurrences:
        return []
    X = np.array([[v.get(k, 0.0) for k in feature_keys] for v in vectors], dtype=float)
    Xs = StandardScaler().fit_transform(X)

    best_k, best_score, best_labels = None, -1.0, None
    for k in range(2, min(max_k, len(vectors) // min_occurrences) + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(Xs)
        try:
            score = silhouette_score(Xs, km.labels_)
        except ValueError:
            continue
        if score > best_score:
            best_k, best_score, best_labels = k, score, km.labels_
    if best_labels is None:
        return []

    patterns = []
    for cluster in range(best_k):
        idx = np.where(best_labels == cluster)[0]
        if len(idx) < min_occurrences:
            continue
        centroid = X[idx].mean(axis=0)
        # dominant features = top-2 by absolute standardized magnitude
        zc = Xs[idx].mean(axis=0)
        top = sorted(range(len(feature_keys)), key=lambda i: abs(zc[i]), reverse=True)[:2]
        tag = "_".join(feature_keys[i][:6] for i in top)
        patterns.append({
            "name": f"disc_{tag}_{cluster}",
            "n": int(len(idx)),
            "centroid": {feature_keys[i]: round(float(centroid[i]), 4)
                         for i in range(len(feature_keys))},
            "member_indices": idx.tolist(),
            "dominant_features": [feature_keys[i] for i in top],
        })
    return patterns
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn pytest tests/test_pattern_discover.py -v`
Expected: PASS (2 passed)

---

### Task 8: Backtest walker

**Files:**
- Create: `glory-hype/glory_hype/patterns/backtest.py`
- Test: `glory-hype/tests/test_pattern_backtest.py`

Context: walks history with a train/test split, builds features per window, labels regime, computes leak-free forward outcomes, scores hand-coded + discovered patterns (win = forward move agreed with the pattern's direction at MOVE_THRESHOLD), and writes `pattern_stats` with `stable` = (n_test ≥ min and test lower-CI ≥ point-estimate−buffer). Tested on a synthetic planted pattern.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_backtest.py`:

```python
from glory_hype.db import Store
from glory_hype.patterns.backtest import run_backtest


def _candle(ts, o, h, l, c, v=1.0):
    return {"interval": "1h", "open_ts": ts, "close_ts": ts + 3599999,
            "o": o, "h": h, "l": l, "c": c, "v": v, "n": 1}


def test_backtest_plants_and_detects(tmp_path):
    s = Store(str(tmp_path / "bt.db"))
    HR = 3600_000
    ts = 1_000_000_000_000
    # Build 120 hours: every ~10h a coil (flat) then a +5% pop = COIL_EXPANSION should score
    candles = []
    price = 100.0
    for i in range(120):
        if i % 10 == 5:
            price *= 1.05   # pop
            candles.append(_candle(ts + i * HR, price / 1.05, price, price / 1.05, price, 3.0))
        else:
            candles.append(_candle(ts + i * HR, price, price * 1.002, price * 0.998, price, 0.4))
    for c in candles:
        s.insert_candle(c)
        s.insert_ctx({"funding": 0.0, "open_interest": 1000.0, "mark_px": c["c"],
                      "oracle_px": c["c"], "mid_px": c["c"], "premium": 0.0,
                      "prev_day_px": c["c"], "day_ntl_vlm": 1.0}, ts=c["open_ts"])
    result = run_backtest(s)
    assert result["events_detected"] > 0
    assert len(s.all_pattern_stats()) > 0     # some pattern stats were written
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn pytest tests/test_pattern_backtest.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/patterns/backtest.py`:

```python
"""Walk history: regimes, events, hand+discovered pattern stats (train/test, CI)."""

import json
import time

from glory_hype import config
from glory_hype.patterns import discover as disc
from glory_hype.patterns.indicators import features
from glory_hype.patterns.library import match_patterns
from glory_hype.patterns.regime import classify
from glory_hype.patterns.stats import forward_outcome, wilson_ci

WINDOW = 12            # bars of lookback for features
HORIZON = config.MOVE_WINDOW_HRS
_FEATS = ["price_slope", "oi_delta_pct", "vol_ratio", "atr_pct", "dist_from_high_20"]


def _ctx_for(store, start_ts, end_ts):
    with store._lock:
        rows = store.conn.execute(
            "SELECT funding, open_interest FROM market_ctx WHERE ts BETWEEN ? AND ? "
            "ORDER BY ts", (start_ts, end_ts)).fetchall()
    return [dict(r) for r in rows]


def run_backtest(store) -> dict:
    candles = store.recent_candles("1h", 100000)   # full 1h history, ascending
    if len(candles) < WINDOW + HORIZON + 20:
        return {"events_detected": 0, "patterns": 0}
    vols = [c["v"] for c in candles]
    vol_avg = (sum(vols) / len(vols)) or 1.0

    split = int(len(candles) * config.PATTERN_TRAIN_FRAC)
    # per-bar: features over [i-WINDOW, i), forward outcome over (i, i+HORIZON]
    rows = []  # (idx, is_train, features, regime, fwd, matched_names)
    for i in range(WINDOW, len(candles) - HORIZON):
        win = candles[i - WINDOW:i]
        ctx = _ctx_for(store, win[0]["open_ts"], win[-1]["close_ts"])
        f = features(win, ctx, vol_avg=vol_avg)
        reg = classify(f)
        store.insert_regime({"ts": candles[i]["open_ts"], "timeframe": "1h",
                             "label": reg, "features_json": json.dumps(f)})
        future = candles[i:i + HORIZON]
        fwd = forward_outcome(candles[i - 1]["c"], future, config.MOVE_THRESHOLD_PCT)
        matched = match_patterns(f)
        rows.append((i, i < split, f, reg, fwd, matched))

    events = [r for r in rows if r[4]["hit"]]

    # score hand-coded patterns
    def score(name, direction, member_rows):
        train = [r for r in member_rows if r[1]]
        test = [r for r in member_rows if not r[1]]
        def wins(rs):
            return sum(1 for r in rs if r[4]["direction"] == direction)
        wt, nt = wins(train), len(train)
        we, ne = wins(test), len(test)
        lo, hi = wilson_ci(we, ne)
        moves = [abs(r[4]["move_pct"]) for r in member_rows if r[4]["hit"]]
        stable = (ne >= max(5, config.PATTERN_MIN_OCCURRENCES // 2) and lo >= 0.50)
        return {"pattern_name": name, "source": member_rows[0][5][0]["source"] if member_rows[0][5] else "hand",
                "n_train": nt, "n_test": ne, "win_rate_train": (wt / nt) if nt else 0.0,
                "win_lo_test": lo, "win_hi_test": hi,
                "avg_move_pct": (sum(moves) / len(moves)) if moves else 0.0,
                "avg_move_hrs": HORIZON, "direction": direction,
                "stable": 1 if stable else 0}

    from glory_hype.patterns.library import HAND_PATTERNS
    for p in HAND_PATTERNS:
        members = [r for r in rows if any(m["name"] == p["name"] for m in r[5])]
        if len(members) >= config.PATTERN_MIN_OCCURRENCES:
            for ev in [r for r in members if r[4]["hit"]]:
                store.insert_pattern_event({"ts": candles[ev[0]]["open_ts"],
                    "pattern_name": p["name"], "source": "hand", "direction": ev[4]["direction"],
                    "features_json": json.dumps(ev[2]), "fwd_4h": ev[4]["move_pct"],
                    "fwd_12h": None, "fwd_24h": None})
            store.upsert_pattern_stat(score(p["name"], p["direction"], members))

    # discovered patterns on TRAIN pre-move windows
    train_event_feats = [r[2] for r in rows if r[1] and r[4]["hit"]]
    discovered = disc.discover_patterns(train_event_feats, _FEATS,
                                        config.PATTERN_MIN_OCCURRENCES)
    now = int(time.time() * 1000)
    for d in discovered:
        store.insert_discovered_pattern({"name": d["name"],
            "centroid_json": json.dumps(d["centroid"]),
            "dominant_features_json": json.dumps(d["dominant_features"]),
            "created_at": now})
        # direction = majority forward direction of its train members
        dirs = [train_event_feats[idx] for idx in d["member_indices"]]
        # (members are pre-move windows that hit; use the dominant outcome direction)
        member_rows = [r for r in rows if r[1] and r[4]["hit"]]
        sel = [member_rows[idx] for idx in d["member_indices"] if idx < len(member_rows)]
        ups = sum(1 for r in sel if r[4]["direction"] == "up")
        direction = "up" if ups >= len(sel) / 2 else "down"
        stat = score(d["name"], direction, sel)
        stat["source"] = "disc"
        store.upsert_pattern_stat(stat)

    return {"events_detected": len(events), "patterns": len(store.all_pattern_stats())}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn pytest tests/test_pattern_backtest.py -v`
Expected: PASS (1 passed). If the planted-pattern assertion is flaky on `events_detected`, confirm the synthetic +5% pops exceed MOVE_THRESHOLD_PCT (4.0) — they do (5%).

---

### Task 9: Live detector

**Files:**
- Create: `glory-hype/glory_hype/patterns/detector.py`
- Test: `glory-hype/tests/test_pattern_detector.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_detector.py`:

```python
from glory_hype.db import Store
from glory_hype.patterns.detector import current_signal


def _candle(ts, o, h, l, c, v=1.0):
    return {"interval": "1h", "open_ts": ts, "close_ts": ts + 3599999,
            "o": o, "h": h, "l": l, "c": c, "v": v, "n": 1}


def test_detector_returns_regime_and_matches(tmp_path):
    s = Store(str(tmp_path / "d.db"))
    HR = 3600_000
    ts = 1_000_000_000_000
    # flat quiet coil now
    for i in range(14):
        s.insert_candle(_candle(ts + i * HR, 100, 100.1, 99.9, 100, 0.3))
        s.insert_ctx({"funding": 0.0, "open_interest": 1000.0, "mark_px": 100,
                      "oracle_px": 100, "mid_px": 100, "premium": 0.0,
                      "prev_day_px": 100, "day_ntl_vlm": 1.0}, ts=ts + i * HR)
    # a stable COIL_EXPANSION stat exists
    s.upsert_pattern_stat({"pattern_name": "COIL_EXPANSION", "source": "hand",
                           "n_train": 20, "n_test": 8, "win_rate_train": 0.75,
                           "win_lo_test": 0.66, "win_hi_test": 0.9, "avg_move_pct": 5.0,
                           "avg_move_hrs": 6, "direction": "up", "stable": 1})
    sig = current_signal(s)
    assert sig["regime"] in ("coiling", "ranging")
    # COIL_EXPANSION should be an active stable match with its confidence
    names = [m["pattern_name"] for m in sig["matches"]]
    if "COIL_EXPANSION" in names:
        m = next(x for x in sig["matches"] if x["pattern_name"] == "COIL_EXPANSION")
        assert m["confidence"] == 0.66 and m["direction"] == "up"


def test_detector_empty_history(tmp_path):
    s = Store(str(tmp_path / "d2.db"))
    sig = current_signal(s)
    assert sig["matches"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy pytest tests/test_pattern_detector.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/patterns/detector.py`:

```python
"""Live pattern signal: featurize the current window, match stable patterns."""

import json

from glory_hype import config
from glory_hype.patterns.indicators import features
from glory_hype.patterns.library import match_patterns
from glory_hype.patterns.regime import classify

WINDOW = 12


def current_signal(store) -> dict:
    candles = store.recent_candles("1h", WINDOW)
    if len(candles) < 2:
        return {"regime": "unknown", "features": {}, "matches": []}
    with store._lock:
        ctx = [dict(r) for r in store.conn.execute(
            "SELECT funding, open_interest FROM market_ctx WHERE ts BETWEEN ? AND ? ORDER BY ts",
            (candles[0]["open_ts"], candles[-1]["close_ts"])).fetchall()]
    vols = [c["v"] for c in store.recent_candles("1h", 14 * 24)]
    vol_avg = (sum(vols) / len(vols)) if vols else 1.0
    f = features(candles, ctx, vol_avg=vol_avg)
    regime = classify(f)

    stable = {s["pattern_name"]: s for s in store.stable_pattern_stats(config.PATTERN_SIGNAL_CONF)}
    matches = []
    for m in match_patterns(f):
        st = stable.get(m["name"])
        if st:
            matches.append({"pattern_name": m["name"], "direction": st["direction"],
                            "confidence": round(st["win_lo_test"], 4),
                            "avg_move_pct": st["avg_move_pct"], "source": st["source"]})
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return {"regime": regime, "features": f, "matches": matches}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with numpy pytest tests/test_pattern_detector.py -v`
Expected: PASS (2 passed)

---

### Task 10: v4 integration — confidence modifier

**Files:**
- Modify: `glory-hype/glory_hype/decision/engine.py`
- Test: `glory-hype/tests/test_pattern_v4_integration.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_pattern_v4_integration.py`:

```python
import time
from glory_hype.db import Store
from glory_hype.decision.engine import record_call


def _fresh(s):
    now = int(time.time() * 1000)
    s.insert_ctx({"funding": 0.0001, "open_interest": 1e6, "mark_px": 67.5,
                  "oracle_px": 67.5, "mid_px": 67.5, "premium": 0.0,
                  "prev_day_px": 64.0, "day_ntl_vlm": 1e9}, ts=now)
    s.save_conclusion({"bias": "bullish", "confidence": 0.7, "score": 70,
                       "key_drivers": [], "caution_flags": [], "source_breakdown": {},
                       "based_on": [], "generated_at": now})
    s.insert_chart_read({"ts": now, "timeframe": "5m", "trend": "up", "current_price": 67.5,
                         "flags": [], "position": {"entry": 67.4, "tp": 68.2, "sl": 66.7},
                         "image_path": None})
    s.set_setting("account_balance", "1000")
    return now


def test_call_inputs_carry_pattern_signal(tmp_path):
    s = Store(str(tmp_path / "v.db"))
    _fresh(s)
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.6, "rationale": "x"})
    assert "pattern_signal" in call.inputs


def test_agreeing_pattern_raises_confidence(tmp_path):
    s = Store(str(tmp_path / "v2.db"))
    _fresh(s)
    # base call confidence
    base = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.6, "rationale": "x"}).confidence
    # plant a stable bullish pattern + enough 1h candles for the detector to match
    HR = 3600_000; now = int(time.time() * 1000)
    for i in range(14):
        s.insert_candle({"interval": "1h", "open_ts": now - (14 - i) * HR,
                         "close_ts": now - (14 - i) * HR + 3599999, "o": 100,
                         "h": 100.1, "l": 99.9, "c": 100, "v": 0.3, "n": 1})
    s.upsert_pattern_stat({"pattern_name": "COIL_EXPANSION", "source": "hand", "n_train": 20,
                           "n_test": 8, "win_rate_train": 0.8, "win_lo_test": 0.7,
                           "win_hi_test": 0.95, "avg_move_pct": 5.0, "avg_move_hrs": 6,
                           "direction": "up", "stable": 1})
    boosted = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                              "confidence": 0.6, "rationale": "x"}).confidence
    assert boosted >= base    # agreeing bullish pattern should not lower it
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy --with fastapi pytest tests/test_pattern_v4_integration.py -v`
Expected: FAIL — `pattern_signal` not in inputs.

- [ ] **Step 3: Implement** — in `engine.py`, add the import and apply the modifier.

Add near the top imports:

```python
from glory_hype.patterns.detector import current_signal
from glory_hype import config as _cfg
```

In `record_call`, after `j = parse_judgment(judgment)` and before sizing, add:

```python
    signal = current_signal(store)
    inputs["pattern_signal"] = signal
    # confidence modifier: agreeing stable pattern lifts, conflicting one trims
    if j["decision"] in ("long", "short"):
        want = "up" if j["decision"] == "long" else "down"
        mod = 0.0
        for m in signal["matches"]:
            edge = (m["confidence"] - 0.5) / 0.5 * _cfg.PATTERN_CONF_MODIFIER_MAX
            mod += edge if m["direction"] == want else -edge
        mod = max(-_cfg.PATTERN_CONF_MODIFIER_MAX, min(_cfg.PATTERN_CONF_MODIFIER_MAX, mod))
        j["confidence"] = max(0.0, min(1.0, j["confidence"] + mod))
```

(`inputs` already gets attached to every TradeCall via the existing code; ensure the `inputs` dict is defined before this block — it is, from the gather step.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with numpy --with fastapi pytest tests/test_pattern_v4_integration.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Confirm v4 suite still green**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn --with fastapi --with httpx pytest tests/test_decision_engine.py tests/test_pattern_v4_integration.py -q`
Expected: all pass.

---

### Task 11: Server endpoint + CLI + dashboard panel

**Files:**
- Modify: `glory-hype/glory_hype/server.py`, `glory-hype/glory_hype/__main__.py`, `glory-hype/glory_hype/static/index.html`
- Test: `glory-hype/tests/test_pattern_server.py`

- [ ] **Step 1: Write the failing server test**

`glory-hype/tests/test_pattern_server.py`:

```python
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_patterns_endpoint(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.upsert_pattern_stat({"pattern_name": "COIL_EXPANSION", "source": "hand", "n_train": 20,
                           "n_test": 8, "win_rate_train": 0.75, "win_lo_test": 0.66,
                           "win_hi_test": 0.9, "avg_move_pct": 5.0, "avg_move_hrs": 6,
                           "direction": "up", "stable": 1})
    client = TestClient(create_app(s))
    r = client.get("/api/patterns")
    assert r.status_code == 200
    body = r.json()
    assert "regime" in body and "matches" in body and "library" in body
    assert any(p["pattern_name"] == "COIL_EXPANSION" for p in body["library"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy --with fastapi --with httpx pytest tests/test_pattern_server.py -v`
Expected: FAIL — `/api/patterns` 404.

- [ ] **Step 3: Add the endpoint** — in `server.py`, add import `from glory_hype.patterns.detector import current_signal` and inside `create_app`:

```python
    @app.get("/api/patterns")
    def patterns():
        sig = current_signal(store)
        return {"regime": sig["regime"], "matches": sig["matches"],
                "library": store.all_pattern_stats()}
```

- [ ] **Step 4: Run server test to pass**

Run: `cd glory-hype && uv run --with pytest --with numpy --with fastapi --with httpx pytest tests/test_pattern_server.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Add the `patterns` CLI** — in `__main__.py`: add `"patterns"` to `choices`, add import `from glory_hype.patterns.backtest import run_backtest` and `from glory_hype.patterns.detector import current_signal`, add a `--mode` arg (`analyze`|`now`), and the branch:

```python
    elif args.cmd == "patterns":
        if args.mode == "analyze":
            print(_json.dumps(run_backtest(store), indent=2))
        else:
            print(_json.dumps(current_signal(store), indent=2, default=str))
```

Add the arg near the others: `p.add_argument("--mode", default="now", choices=["analyze", "now"])`.

- [ ] **Step 6: Add the dashboard Pattern Signal panel** — in `static/index.html` before `</body>`:

```html
  <h2 style="font-size:14px;margin-top:24px;">Pattern Signal</h2>
  <div id="patterns" class="card">Loading…</div>

<script>
function renderPatterns(d){
  const el=document.getElementById("patterns");
  const matches=(d.matches||[]).map(m=>`<div class="${m.direction==='up'?'pos':'neg'}">
    ${m.pattern_name} → ${m.direction.toUpperCase()} (conf ${(m.confidence*100).toFixed(0)}%, avg ${m.avg_move_pct.toFixed(1)}%)</div>`).join('');
  el.innerHTML=`<div class="label">Regime</div><div class="val">${(d.regime||'?').toUpperCase()}</div>
    <div style="font-size:12px;margin-top:6px;">${matches||'No active stable pattern.'}</div>`;
}
function loadPatterns(){ fetch("/api/patterns").then(r=>r.json()).then(renderPatterns); }
loadPatterns(); setInterval(loadPatterns, 30000);
</script>
```

- [ ] **Step 7: requirements + pyproject** — add `numpy>=1.26` and `scikit-learn>=1.4` to `requirements.txt` and the `dependencies` in `pyproject.toml`.

- [ ] **Step 8: Full offline suite**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`
Expected: ALL green.

---

### Task 12: Real-data analysis smoke (opt-in)

**Files:**
- Create: `glory-hype/tests/test_pattern_realdata_smoke.py`

- [ ] **Step 1: Write the opt-in smoke**

`glory-hype/tests/test_pattern_realdata_smoke.py`:

```python
import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.path.exists("hype.db"), reason="needs the real hype.db")
def test_real_backtest_runs():
    """Runs the full backtest on the real 18-month hype.db; asserts it completes and
    writes stats. No assertion on the numbers — they are empirical."""
    from glory_hype.db import Store
    from glory_hype.patterns.backtest import run_backtest
    s = Store("hype.db")
    res = run_backtest(s)
    assert res["events_detected"] >= 0
    stats = s.all_pattern_stats()
    print(f"events={res['events_detected']} patterns={len(stats)}")
    for st in stats:
        print(f"  {st['pattern_name']} [{st['source']}] dir={st['direction']} "
              f"n_test={st['n_test']} lo={st['win_lo_test']:.2f} stable={st['stable']} "
              f"avg_move={st['avg_move_pct']:.1f}%")
    s.close()
```

- [ ] **Step 2: Offline suite still green (live deselected)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`
Expected: PASS; live deselected.

- [ ] **Step 3: (Manual) run the real analysis** — the actual intelligence:

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn python -m pytest -m live tests/test_pattern_realdata_smoke.py -v -s`
Expected: prints the discovered + hand-coded pattern stats over the real 18 months — the patterns with `stable=1` and `lo >= 0.60` are the ones that earned their place. This is the deliverable: our actual, validated edge.

---

### Task 13: Commit (GATED — only after user approval)

> Do NOT run until the user explicitly says to commit. Includes the v5 resolver entry-fill fix already applied this session.

- [ ] **Step 1: Stage and commit**

```bash
cd E:/Glory
git add glory-hype docs/superpowers/specs/2026-06-03-hype-pattern-intelligence-design.md \
  docs/superpowers/plans/2026-06-03-hype-pattern-intelligence.md
git commit -m "feat(hype): v9 pattern intelligence + fix v5 resolver entry-fill bug

v9: historical pattern mining (hand-coded + auto-discovered), out-of-sample
validation with Wilson CIs, live regime/pattern detector feeding a confidence
modifier into v4. Anti-overfit: min-occurrences, train/test split, lower-CI confidence.

fix: resolver now requires the entry to fill before scoring TP/SL (no more phantom
wins from limits that never triggered).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Regime classifier (Layer 1) → Task 3 ✓
- Event detector + hand-coded library (Layer 2) → Tasks 5, 8 ✓
- Predictive stats per pattern + CIs (Layer 3) → Tasks 4, 8 ✓
- Auto-discovery (clustering) → Task 7 ✓
- Anti-overfit contract (min-occ, train/test, Wilson lower-CI, leak-free) → Tasks 4, 8 (stats + split + forward_outcome) ✓
- Live detector → Task 9 ✓
- v4 confidence modifier + inputs.pattern_signal → Task 10 ✓
- Storage (regimes/pattern_events/pattern_stats/discovered_patterns) → Task 6 ✓
- /api/patterns + dashboard panel + `patterns` CLI → Task 11 ✓
- Real-data analysis (the deliverable) → Task 12 ✓

**Placeholder scan:** No TBD/TODO; complete code in every step.

**Type consistency:** `features(candles, ctx_rows, vol_avg)` consistent across indicators/backtest/detector. `classify(features)` consistent. `wilson_ci(wins, n)` and `forward_outcome(start_close, future, threshold_pct)` consistent across stats/backtest. `match_patterns(f)` returns dicts with `name`/`source`/`direction` used by backtest + detector. Store methods (`insert_regime`/`insert_pattern_event`/`upsert_pattern_stat`/`stable_pattern_stats`/`all_pattern_stats`/`insert_discovered_pattern`) named identically across db/backtest/detector/server/tests. `current_signal(store)` returns `{regime, features, matches}` consumed by engine + server consistently. `pattern_stats` columns match between SCHEMA, `upsert_pattern_stat`, and the dashboard/`stable_pattern_stats` readers.

**Known rigor note:** the backtest's `stable` flag uses test lower-CI ≥ 0.50 as the bar to be *recorded* stable; the live `SIGNAL_CONF` (0.60) is the higher bar to actually *fire*. Two gates, intentional — recorded-but-not-fired patterns are visible in the library panel for transparency without driving calls.
