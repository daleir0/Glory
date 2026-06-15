# HYPE Event-Anchored Intelligence (v9.2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Curate HYPE's catalyst history, study price/funding/OI behavior in the window around past events (the playbook), and surface a forward alert for upcoming catalysts (June 6 unlock) — feeding a v4 caution and an Intel-tab Events panel.

**Architecture:** A new `events/` subpackage: a curated `events` table (seeded with the real monthly-6th unlocks + ETF launches), a pure `eventstudy` analyzer (normalized ±7d window + median composite per type with honest N labels), and a `upcoming` forward alert. Integrates into v4 (event_context + 48h caution) and the dashboard Intel tab.

**Tech Stack:** Python 3.12, `uv`, stdlib `sqlite3`, `fastapi`, `pytest`. No new external deps.

**Real catalog (researched this session — HYPE team vesting unlocks on the 6th of each month since Jan 2026):**
- Unlocks: 2026-01-06, 2026-02-06, 2026-03-06, 2026-04-06, 2026-05-06 (studiable past), **2026-06-06 (future, ~9.92M HYPE / ~2.54% supply / ~$684M)**
- ETF/approval: 2026-05-18 SpaceX perp listing, ~2026-05-26 CFTC regulated-perp approval, 2026-06-03 Grayscale HYPG ETF on Nasdaq

> **Git note:** prior work committed through 089e869c. Do NOT commit per-task. Final commit (Task 9) is gated on explicit user approval.

Run offline tests with:
`cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`

---

## File Structure

```
glory-hype/glory_hype/events/
  __init__.py
  catalog.py      # SEED list + seed_catalog(store) + add helper
  eventstudy.py   # pure: study_event, composite
  upcoming.py     # forward alert: upcoming_events
glory-hype/glory_hype/
  config.py       # MODIFY: EVENT_WINDOW_DAYS, EVENT_ALERT_DAYS, EVENT_CAUTION_HRS
  db.py           # MODIFY: events + event_studies tables + methods
  decision/engine.py  # MODIFY: event_context input + 48h caution
  server.py       # MODIFY: /api/events
  static/index.html   # MODIFY: Events panel in Intel tab
  __main__.py     # MODIFY: `events` subcommand
glory-hype/tests/
  test_event_catalog.py
  test_eventstudy.py
  test_event_upcoming.py
  test_event_store.py
  test_event_v4.py
  test_event_server.py
```

---

### Task 1: Config

**Files:**
- Modify: `glory-hype/glory_hype/config.py`

- [ ] **Step 1: Append to `config.py`**

```python
# --- v9.2 event-anchored intelligence ---
EVENT_WINDOW_DAYS = 7        # +/- window around an event for the study
EVENT_ALERT_DAYS = 14        # show upcoming events within this horizon
EVENT_CAUTION_HRS = 48       # a major event within this many hours -> v4 caution
EVENT_PROXIMITY_DAYS = 3     # proximity flag threshold
```

- [ ] **Step 2: Verify**

Run: `cd glory-hype && uv run python -c "from glory_hype import config; print(config.EVENT_WINDOW_DAYS, config.EVENT_CAUTION_HRS)"`
Expected: `7 48`

---

### Task 2: Event store

**Files:**
- Modify: `glory-hype/glory_hype/db.py`
- Test: `glory-hype/tests/test_event_store.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_event_store.py`:

```python
from glory_hype.db import Store


def test_insert_and_query_events(tmp_path):
    s = Store(str(tmp_path / "e.db"))
    s.insert_event({"date_ms": 1000, "type": "unlock", "label": "Jan unlock",
                    "magnitude_pct": 0.5, "magnitude_usd": 1e6, "source_url": "u",
                    "notes": "n"})
    s.insert_event({"date_ms": 9_000_000_000_000, "type": "unlock",
                    "label": "future unlock", "magnitude_pct": 2.5,
                    "magnitude_usd": 6.8e8, "source_url": "u2", "notes": ""})
    assert len(s.all_events()) == 2
    assert len(s.events_of_type("unlock")) == 2
    up = s.upcoming_events_raw(now_ms=2000, horizon_days=365 * 100)
    assert len(up) == 1 and up[0]["label"] == "future unlock"


def test_event_study_roundtrip(tmp_path):
    s = Store(str(tmp_path / "e2.db"))
    s.upsert_event_study({"type": "unlock", "n": 5, "median_pre": -3.0,
                          "median_post": 4.0, "median_trough": -6.0,
                          "median_peak": 5.0, "spread_json": "{}",
                          "confidence_label": "small-sample composite (N=5)",
                          "computed_at": 1})
    st = s.event_study("unlock")
    assert st["n"] == 5 and st["median_pre"] == -3.0
    assert s.all_event_studies()[0]["type"] == "unlock"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_event_store.py -v`
Expected: FAIL — methods missing.

- [ ] **Step 3: Add tables to SCHEMA** — append to `db.py` SCHEMA:

```sql
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_ms INTEGER, type TEXT, label TEXT, magnitude_pct REAL,
    magnitude_usd REAL, source_url TEXT, notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date_ms);
CREATE TABLE IF NOT EXISTS event_studies (
    type TEXT PRIMARY KEY, n INTEGER, median_pre REAL, median_post REAL,
    median_trough REAL, median_peak REAL, spread_json TEXT,
    confidence_label TEXT, computed_at INTEGER
);
```

- [ ] **Step 4: Add Store methods** (in `db.py`):

```python
    def insert_event(self, e: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT INTO events
                   (date_ms, type, label, magnitude_pct, magnitude_usd, source_url, notes)
                   VALUES (?,?,?,?,?,?,?)""",
                (e["date_ms"], e.get("type"), e.get("label"), e.get("magnitude_pct"),
                 e.get("magnitude_usd"), e.get("source_url"), e.get("notes", "")))
            self.conn.commit()

    def all_events(self) -> list:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM events ORDER BY date_ms").fetchall()
        return [dict(r) for r in rows]

    def events_of_type(self, type_: str) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE type=? ORDER BY date_ms", (type_,)).fetchall()
        return [dict(r) for r in rows]

    def upcoming_events_raw(self, now_ms: int, horizon_days: int) -> list:
        hi = now_ms + horizon_days * 86400_000
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE date_ms > ? AND date_ms <= ? ORDER BY date_ms",
                (now_ms, hi)).fetchall()
        return [dict(r) for r in rows]

    def event_exists(self, date_ms: int, type_: str) -> bool:
        with self._lock:
            r = self.conn.execute(
                "SELECT 1 FROM events WHERE date_ms=? AND type=? LIMIT 1",
                (date_ms, type_)).fetchone()
        return r is not None

    def upsert_event_study(self, st: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO event_studies
                   (type, n, median_pre, median_post, median_trough, median_peak,
                    spread_json, confidence_label, computed_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (st["type"], st["n"], st.get("median_pre"), st.get("median_post"),
                 st.get("median_trough"), st.get("median_peak"),
                 st.get("spread_json", "{}"), st.get("confidence_label"),
                 st.get("computed_at", 0)))
            self.conn.commit()

    def event_study(self, type_: str):
        with self._lock:
            r = self.conn.execute(
                "SELECT * FROM event_studies WHERE type=?", (type_,)).fetchone()
        return dict(r) if r else None

    def all_event_studies(self) -> list:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM event_studies").fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_event_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Full suite (no regression)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`
Expected: all prior pass.

---

### Task 3: Curated catalog + seed

**Files:**
- Create: `glory-hype/glory_hype/events/__init__.py`, `glory-hype/glory_hype/events/catalog.py`
- Test: `glory-hype/tests/test_event_catalog.py`

- [ ] **Step 1: Create the package init**

`glory-hype/glory_hype/events/__init__.py`:

```python
"""HYPE event-anchored intelligence (v9.2): curated catalysts + event study."""
```

- [ ] **Step 2: Write the failing test**

`glory-hype/tests/test_event_catalog.py`:

```python
from glory_hype.db import Store
from glory_hype.events.catalog import SEED_EVENTS, seed_catalog


def test_seed_has_monthly_unlocks_and_future():
    types = [e["type"] for e in SEED_EVENTS]
    assert types.count("unlock") >= 6     # Jan-Jun monthly unlocks
    # the June 6 future unlock is present
    assert any("2026-06-06" in e["date"] and e["type"] == "unlock" for e in SEED_EVENTS)


def test_seed_catalog_idempotent(tmp_path):
    s = Store(str(tmp_path / "c.db"))
    n1 = seed_catalog(s)
    n2 = seed_catalog(s)        # second run inserts nothing (dedup by date+type)
    assert n1 == len(SEED_EVENTS)
    assert n2 == 0
    assert len(s.all_events()) == len(SEED_EVENTS)
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_event_catalog.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement**

`glory-hype/glory_hype/events/catalog.py`:

```python
"""Curated HYPE catalyst catalog. Hand-verified; data decides nothing here — these are
facts we maintain. Dates are UTC. Magnitudes are best-known and flagged for verification."""

from datetime import datetime, timezone

# HYPE team vesting unlocks land on the 6th of each month (first Jan 6 2026).
# ETF/approval catalysts from project research. magnitude_pct = % of supply where known.
SEED_EVENTS = [
    {"date": "2026-01-06", "type": "unlock", "label": "Team vesting unlock (Jan)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th"},
    {"date": "2026-02-06", "type": "unlock", "label": "Team vesting unlock (Feb)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th"},
    {"date": "2026-03-06", "type": "unlock", "label": "Team vesting unlock (Mar)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th"},
    {"date": "2026-04-06", "type": "unlock", "label": "Team vesting unlock (Apr)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th"},
    {"date": "2026-05-06", "type": "unlock", "label": "Team vesting unlock (May)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th"},
    {"date": "2026-06-06", "type": "unlock", "label": "Team vesting unlock (Jun) — UPCOMING",
     "magnitude_pct": 2.54, "magnitude_usd": 6.84e8,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events",
     "notes": "~9.92M HYPE; verify magnitude on the day"},
    {"date": "2026-05-18", "type": "listing", "label": "SpaceX pre-IPO perp listing",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "", "notes": "drove +7% vs down market"},
    {"date": "2026-05-26", "type": "etf", "label": "CFTC regulated-perp approval",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "", "notes": "drove ATH push"},
    {"date": "2026-06-03", "type": "etf", "label": "Grayscale HYPG ETF on Nasdaq",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "", "notes": "institutional on-ramp; drove the Jun 3 rally"},
]


def _to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def seed_catalog(store) -> int:
    """Insert any SEED_EVENTS not already present (dedup by date+type). Returns count added."""
    added = 0
    for e in SEED_EVENTS:
        ms = _to_ms(e["date"])
        if store.event_exists(ms, e["type"]):
            continue
        store.insert_event({"date_ms": ms, "type": e["type"], "label": e["label"],
                            "magnitude_pct": e["magnitude_pct"],
                            "magnitude_usd": e["magnitude_usd"],
                            "source_url": e["source_url"], "notes": e["notes"]})
        added += 1
    return added
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_event_catalog.py -v`
Expected: PASS (2 passed)

---

### Task 4: Event-study analyzer (pure)

**Files:**
- Create: `glory-hype/glory_hype/events/eventstudy.py`
- Test: `glory-hype/tests/test_eventstudy.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_eventstudy.py`:

```python
from glory_hype.events.eventstudy import study_event, composite

HR = 3600_000


def _candle(ts, c):
    return {"interval": "1h", "open_ts": ts, "close_ts": ts + HR - 1,
            "o": c, "h": c * 1.001, "l": c * 0.999, "c": c, "v": 1.0, "n": 1}


def test_study_event_pre_post():
    event_ms = 1_000_000_000_000
    # window -2h..+2h: price 100 (pre) dips to 96 at event, recovers to 102 after
    candles = [_candle(event_ms - 2 * HR, 100.0), _candle(event_ms - HR, 98.0),
               _candle(event_ms, 96.0), _candle(event_ms + HR, 99.0),
               _candle(event_ms + 2 * HR, 102.0)]
    st = study_event({"date_ms": event_ms, "type": "unlock"}, candles, [], window_days=1)
    assert round(st["pre_pct"], 1) == -4.0      # 100 -> 96 into the event
    assert round(st["post_pct"], 1) == 6.25     # 96 -> 102 after (rel to event close)
    assert st["trough_pct"] < 0
    assert st["peak_pct"] > 0
    assert st["n_candles"] == 5


def test_study_event_no_data():
    st = study_event({"date_ms": 5, "type": "unlock"}, [], [], window_days=7)
    assert st["n_candles"] == 0
    assert st["pre_pct"] is None


def test_composite_median_and_label():
    studies = [{"pre_pct": -3.0, "post_pct": 4.0, "trough_pct": -6.0, "peak_pct": 5.0},
               {"pre_pct": -5.0, "post_pct": 2.0, "trough_pct": -8.0, "peak_pct": 3.0},
               {"pre_pct": -1.0, "post_pct": 6.0, "trough_pct": -4.0, "peak_pct": 7.0}]
    c = composite(studies, "unlock")
    assert c["n"] == 3
    assert c["median_pre"] == -3.0       # median of -3,-5,-1
    assert "N=3" in c["confidence_label"]


def test_composite_small_n_label():
    c = composite([{"pre_pct": -3.0, "post_pct": 4.0, "trough_pct": -6.0, "peak_pct": 5.0}],
                  "unlock")
    assert c["n"] == 1
    assert "insufficient" in c["confidence_label"].lower()


def test_composite_empty():
    c = composite([], "unlock")
    assert c["n"] == 0
    assert c["median_pre"] is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_eventstudy.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/events/eventstudy.py`:

```python
"""Pure event-study: window behavior around a catalyst + small-N composite.

Descriptive only — no statistical inference. Composite reports median + N honestly."""

import statistics


def study_event(event: dict, candles: list, ctx_rows: list, window_days: int) -> dict:
    """candles: 1h candles (ascending) already sliced near the event (or full — we filter).
    Returns pre/post/trough/peak % relative to the event, and the normalized path."""
    ev = event["date_ms"]
    half = window_days * 86400_000
    win = [c for c in candles if ev - half <= c["open_ts"] <= ev + half]
    if not win:
        return {"pre_pct": None, "post_pct": None, "trough_pct": None,
                "peak_pct": None, "n_candles": 0, "path": []}
    # event close = the candle closest to ev
    ev_candle = min(win, key=lambda c: abs(c["open_ts"] - ev))
    p0 = win[0]["c"]
    pe = ev_candle["c"]
    pend = win[-1]["c"]
    pre_pct = (pe - p0) / p0 * 100
    post_pct = (pend - pe) / pe * 100
    lows = [c["l"] for c in win]
    highs = [c["h"] for c in win]
    trough_pct = (min(lows) - pe) / pe * 100
    peak_pct = (max(highs) - pe) / pe * 100
    path = [round((c["c"] - pe) / pe * 100 + 100, 3) for c in win]   # normalized to 100 at event
    return {"pre_pct": pre_pct, "post_pct": post_pct, "trough_pct": trough_pct,
            "peak_pct": peak_pct, "n_candles": len(win), "path": path}


def _median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def composite(studies: list, type_: str) -> dict:
    usable = [s for s in studies if s.get("pre_pct") is not None]
    n = len(usable)
    if n == 0:
        return {"type": type_, "n": 0, "median_pre": None, "median_post": None,
                "median_trough": None, "median_peak": None, "spread": {},
                "confidence_label": "no studiable history"}
    label = (f"small-sample composite (N={n})" if n >= 3
             else f"insufficient history — directional only (N={n})")
    pres = [s["pre_pct"] for s in usable]
    posts = [s["post_pct"] for s in usable]
    return {"type": type_, "n": n,
            "median_pre": _median(pres), "median_post": _median(posts),
            "median_trough": _median([s["trough_pct"] for s in usable]),
            "median_peak": _median([s["peak_pct"] for s in usable]),
            "spread": {"pre_min": min(pres), "pre_max": max(pres),
                       "post_min": min(posts), "post_max": max(posts)},
            "confidence_label": label}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_eventstudy.py -v`
Expected: PASS (5 passed)

---

### Task 5: Forward alert + analyze orchestration

**Files:**
- Create: `glory-hype/glory_hype/events/upcoming.py`
- Test: `glory-hype/tests/test_event_upcoming.py`

Context: `analyze_events(store)` computes & persists the per-type composites from past
events using our candles; `upcoming_events(store, now, horizon)` returns future catalog
rows with days_until, proximity flag, and the matching composite.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_event_upcoming.py`:

```python
import time
from glory_hype.db import Store
from glory_hype.events.upcoming import analyze_events, upcoming_events

HR = 3600_000


def _candle(ts, c):
    return {"interval": "1h", "open_ts": ts, "close_ts": ts + HR - 1,
            "o": c, "h": c * 1.001, "l": c * 0.999, "c": c, "v": 1.0, "n": 1}


def _seed_unlock_history(s, base, n):
    # n past unlocks, each: dip then recover, spaced 30d apart
    for k in range(n):
        ev = base + k * 30 * 86400_000
        s.insert_event({"date_ms": ev, "type": "unlock", "label": f"unlock {k}",
                        "magnitude_pct": 2.0, "magnitude_usd": 1e8, "source_url": "",
                        "notes": ""})
        for h in range(-48, 49):
            price = 100.0 + (h * -0.05 if h < 0 else h * 0.08)  # dip in, rise out
            s.insert_candle(_candle(ev + h * HR, price))


def test_analyze_builds_composite(tmp_path):
    s = Store(str(tmp_path / "u.db"))
    base = 1_700_000_000_000
    _seed_unlock_history(s, base, 4)
    res = analyze_events(s)
    assert res["types"]["unlock"]["n"] == 4
    st = s.event_study("unlock")
    assert st["n"] == 4 and st["median_pre"] < 0     # dipped into the event


def test_upcoming_attaches_composite_and_flag(tmp_path):
    s = Store(str(tmp_path / "u2.db"))
    base = 1_700_000_000_000
    _seed_unlock_history(s, base, 3)
    analyze_events(s)
    now = base + 100 * 86400_000
    s.insert_event({"date_ms": now + 2 * 86400_000, "type": "unlock",
                    "label": "future unlock", "magnitude_pct": 2.5,
                    "magnitude_usd": 6.8e8, "source_url": "", "notes": ""})
    up = upcoming_events(s, now_ms=now, horizon_days=14)
    assert len(up) == 1
    e = up[0]
    assert e["days_until"] == 2
    assert e["proximity"] is True                    # <= 3 days
    assert e["composite"]["n"] == 3                   # unlock history attached
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_event_upcoming.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/events/upcoming.py`:

```python
"""Compute per-type event-study composites and surface upcoming catalysts."""

import json
import time

from glory_hype import config
from glory_hype.events.eventstudy import composite, study_event


def analyze_events(store) -> dict:
    """Study every PAST event against our candles, build per-type composites, persist."""
    candles = store.recent_candles("1h", 100000)
    now = int(time.time() * 1000)
    by_type = {}
    for e in store.all_events():
        if e["date_ms"] >= now:
            continue   # only past events are studiable
        st = study_event(e, candles, [], config.EVENT_WINDOW_DAYS)
        if st["n_candles"] > 0:
            by_type.setdefault(e["type"], []).append(st)
    out = {}
    for type_, studies in by_type.items():
        c = composite(studies, type_)
        store.upsert_event_study({
            "type": type_, "n": c["n"], "median_pre": c["median_pre"],
            "median_post": c["median_post"], "median_trough": c["median_trough"],
            "median_peak": c["median_peak"], "spread_json": json.dumps(c["spread"]),
            "confidence_label": c["confidence_label"], "computed_at": now})
        out[type_] = c
    return {"types": out}


def upcoming_events(store, now_ms: int, horizon_days: int) -> list:
    rows = store.upcoming_events_raw(now_ms, horizon_days)
    out = []
    for e in rows:
        days = (e["date_ms"] - now_ms) / 86400_000
        st = store.event_study(e["type"])
        out.append({
            "label": e["label"], "type": e["type"], "date_ms": e["date_ms"],
            "days_until": int(days),
            "proximity": days <= config.EVENT_PROXIMITY_DAYS,
            "magnitude_pct": e["magnitude_pct"], "magnitude_usd": e["magnitude_usd"],
            "composite": st if st else {"n": 0, "confidence_label": "no comparable history"},
        })
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_event_upcoming.py -v`
Expected: PASS (2 passed)

---

### Task 6: v4 integration — event_context + 48h caution

**Files:**
- Modify: `glory-hype/glory_hype/decision/engine.py`
- Test: `glory-hype/tests/test_event_v4.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_event_v4.py`:

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


def test_event_context_in_inputs(tmp_path):
    s = Store(str(tmp_path / "v.db"))
    now = _fresh(s)
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.6, "rationale": "x"})
    assert "event_context" in call.inputs


def test_event_within_48h_adds_caution(tmp_path):
    s = Store(str(tmp_path / "v2.db"))
    now = _fresh(s)
    # an unlock 24h out
    s.insert_event({"date_ms": now + 24 * 3600_000, "type": "unlock",
                    "label": "unlock soon", "magnitude_pct": 2.5, "magnitude_usd": 6.8e8,
                    "source_url": "", "notes": ""})
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.6, "rationale": "x"})
    ec = call.inputs["event_context"]
    assert ec["caution"] is True
    assert "unlock" in ec["nearest"]["type"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with numpy --with fastapi pytest tests/test_event_v4.py -v`
Expected: FAIL — `event_context` not in inputs.

- [ ] **Step 3: Implement** — in `engine.py`, add the import and event context.

Add near the top imports:

```python
from glory_hype.events.upcoming import upcoming_events
```

In `record_call`, after `inputs["pattern_signal"] = signal` (or alongside the other input
assembly — place it where `inputs` is already defined and before the call is built), add:

```python
    up = upcoming_events(store, now, config.EVENT_ALERT_DAYS)
    nearest = up[0] if up else None
    caution = bool(nearest and nearest["type"] in ("unlock", "etf")
                   and (nearest["date_ms"] - now) <= config.EVENT_CAUTION_HRS * 3600_000)
    inputs["event_context"] = {"nearest": nearest, "caution": caution}
```

(`config` is already imported in engine.py; `now` and `inputs` already exist.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with numpy --with fastapi pytest tests/test_event_v4.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Confirm v4 suite still green**

Run: `cd glory-hype && uv run --with pytest --with numpy --with scikit-learn --with fastapi --with httpx pytest tests/test_decision_engine.py tests/test_pattern_v4_integration.py tests/test_event_v4.py -q`
Expected: all pass.

---

### Task 7: Server + CLI + dashboard Events panel

**Files:**
- Modify: `glory-hype/glory_hype/server.py`, `glory-hype/glory_hype/__main__.py`, `glory-hype/glory_hype/static/index.html`
- Test: `glory-hype/tests/test_event_server.py`

- [ ] **Step 1: Write the failing server test**

`glory-hype/tests/test_event_server.py`:

```python
import time
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_events_endpoint(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    now = int(time.time() * 1000)
    s.insert_event({"date_ms": now + 2 * 86400_000, "type": "unlock",
                    "label": "future unlock", "magnitude_pct": 2.5,
                    "magnitude_usd": 6.8e8, "source_url": "", "notes": ""})
    s.upsert_event_study({"type": "unlock", "n": 4, "median_pre": -3.0,
                          "median_post": 4.0, "median_trough": -6.0, "median_peak": 5.0,
                          "spread_json": "{}", "confidence_label": "small-sample composite (N=4)",
                          "computed_at": now})
    client = TestClient(create_app(s))
    r = client.get("/api/events")
    assert r.status_code == 200
    body = r.json()
    assert len(body["upcoming"]) == 1
    assert body["upcoming"][0]["type"] == "unlock"
    assert any(p["type"] == "unlock" for p in body["playbook"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_event_server.py -v`
Expected: FAIL — `/api/events` 404.

- [ ] **Step 3: Add the endpoint** — in `server.py`, add import `from glory_hype.events.upcoming import upcoming_events`, `from glory_hype import config as _cfg2` (or reuse existing config import), and inside `create_app`:

```python
    @app.get("/api/events")
    def events():
        import time
        now = int(time.time() * 1000)
        return {"upcoming": upcoming_events(store, now, 30),
                "playbook": store.all_event_studies()}
```

- [ ] **Step 4: Run server test to pass**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_event_server.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Add the `events` CLI** — in `__main__.py`: add `"events"` to `choices`, imports `from glory_hype.events.catalog import seed_catalog`, `from glory_hype.events.upcoming import analyze_events, upcoming_events`, a `--mode` choice extension or new arg. Use a dedicated `--events-mode` to avoid clashing with the patterns `--mode`:

```python
    p.add_argument("--events-mode", default="upcoming",
                   choices=["seed", "analyze", "upcoming"])
```

Add the branch:

```python
    elif args.cmd == "events":
        import time as _t
        if args.events_mode == "seed":
            print(_json.dumps({"added": seed_catalog(store)}, indent=2))
        elif args.events_mode == "analyze":
            print(_json.dumps(analyze_events(store), indent=2, default=str))
        else:
            print(_json.dumps(upcoming_events(store, int(_t.time() * 1000), 30),
                              indent=2, default=str))
```

- [ ] **Step 6: Add the Events panel** to the **Intel** tab in `static/index.html`. Inside the `<div class="tabsec" data-tab="intel">` block, after the Pattern Signal panel, add:

```html
    <h2 class="sub">Events</h2>
    <div id="events" class="card">Loading…</div>
```

And add a script before `</body>`:

```html
<script>
function renderEvents(d){
  const el=document.getElementById("events");
  const up=(d.upcoming||[]).map(e=>{
    const c=e.composite||{};
    const hist=c.n? `history (${c.confidence_label}): ${c.median_pre?.toFixed?.(1)??'—'}% into / ${c.median_post?.toFixed?.(1)??'—'}% after`
                  : 'no comparable history';
    return `<div style="margin-bottom:6px;${e.proximity?'color:#fc5c65;font-weight:bold;':''}">
      ${e.proximity?'⚠️ ':''}${e.label} — in ${e.days_until}d (${e.type})<br>
      <span style="font-size:11px;color:#8b97a7;">${hist}</span></div>`;
  }).join('');
  const pb=(d.playbook||[]).map(p=>
    `<tr><td>${p.type}</td><td>N=${p.n}</td><td class="${p.median_pre<0?'neg':'pos'}">${p.median_pre?.toFixed?.(1)??'—'}%</td>
     <td class="${p.median_post>0?'pos':'neg'}">${p.median_post?.toFixed?.(1)??'—'}%</td></tr>`).join('');
  el.innerHTML=`${up||'No upcoming catalysts.'}
    <table style="margin-top:8px;font-size:11px;"><thead><tr><th>Type</th><th>N</th><th>Pre</th><th>Post</th></tr></thead>
    <tbody>${pb||'<tr><td colspan=4>Run events analyze to build the playbook.</td></tr>'}</tbody></table>`;
}
function loadEvents(){ fetch("/api/events").then(r=>r.json()).then(renderEvents); }
loadEvents(); setInterval(loadEvents, 60000);
</script>
```

- [ ] **Step 7: Full offline suite**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`
Expected: ALL green.

---

### Task 8: Real catalog seed + analysis (the deliverable)

**Files:**
- Create: `glory-hype/tests/test_event_realdata.py`

- [ ] **Step 1: Write the opt-in smoke**

`glory-hype/tests/test_event_realdata.py`:

```python
import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.path.exists("hype.db"), reason="needs the real hype.db")
def test_real_event_study():
    """Seed the real catalog, study past unlocks/ETFs against hype.db, print the playbook
    and the June 6 forward alert. No correctness assertion on the numbers (empirical)."""
    import time
    from glory_hype.db import Store
    from glory_hype.events.catalog import seed_catalog
    from glory_hype.events.upcoming import analyze_events, upcoming_events
    s = Store("hype.db")
    print("seeded:", seed_catalog(s))
    res = analyze_events(s)
    for t, c in res["types"].items():
        print(f"  {t}: {c['confidence_label']} pre={c['median_pre']} post={c['median_post']} "
              f"trough={c['median_trough']} peak={c['median_peak']}")
    print("UPCOMING:")
    for e in upcoming_events(s, int(time.time() * 1000), 30):
        print(f"  {e['label']} in {e['days_until']}d proximity={e['proximity']} "
              f"hist_n={e['composite'].get('n')}")
    s.close()
```

- [ ] **Step 2: Offline suite green (live deselected)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography --with numpy --with scikit-learn pytest -q`
Expected: PASS; live deselected.

- [ ] **Step 3: (Manual) run the real catalog + study — the June 6 playbook**

Run: `cd glory-hype && uv run --with pytest --with numpy python -m pytest -m live tests/test_event_realdata.py -v -s`
Expected: prints the unlock/ETF composites from our real data + the June 6 forward alert with days_until and proximity flag. This is the deliverable: the unlock playbook ready before June 6.

---

### Task 9: Commit (GATED — only after user approval)

> Do NOT run until the user explicitly says to commit.

- [ ] **Step 1: Stage and commit**

```bash
cd E:/Glory
git add glory-hype docs/superpowers/specs/2026-06-03-hype-event-intelligence-design.md \
  docs/superpowers/plans/2026-06-03-hype-event-intelligence.md
git commit -m "feat(hype): v9.2 event-anchored intelligence — catalyst catalog + event study + Jun 6 alert

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Curated catalog + seed (real monthly-6th unlocks + ETFs + future Jun 6) → Task 3 ✓
- Event-study analyzer (window, normalized path, pre/post/trough/peak) → Task 4 ✓
- Composite per type with honest N labels → Task 4 ✓
- Forward alert (countdown + proximity + composite attach) → Task 5 ✓
- v4 event_context + 48h caution → Task 6 ✓
- Storage (events + event_studies) → Task 2 ✓
- /api/events + Intel-tab Events panel + `events` CLI → Task 7 ✓
- Real catalog deliverable (June 6 playbook) → Task 8 ✓
- Honesty (N labels, descriptive, no fake confidence) → Tasks 4, 5 (labels) ✓
- Out of scope (significance testing, scraping, cross-asset) → not built ✓

**Placeholder scan:** No TBD/TODO; complete code in every step; commands have expected output.

**Type consistency:** `study_event(event, candles, ctx_rows, window_days)` → dict with
pre_pct/post_pct/trough_pct/peak_pct/n_candles/path, consumed by `analyze_events` +
`composite`. `composite(studies, type_)` → dict with n/median_*/spread/confidence_label,
persisted via `upsert_event_study` (keys match the SCHEMA columns: type/n/median_pre/
median_post/median_trough/median_peak/spread_json/confidence_label/computed_at). `upcoming_events(store, now_ms, horizon_days)` → list with label/type/date_ms/days_until/
proximity/composite, consumed by v4 (`event_context`), server, dashboard. Store methods
(`insert_event`/`all_events`/`events_of_type`/`upcoming_events_raw`/`event_exists`/
`upsert_event_study`/`event_study`/`all_event_studies`) named identically across
db/catalog/upcoming/server/tests. `seed_catalog(store)` dedups via `event_exists`. CLI uses
`--events-mode` (distinct from patterns `--mode`) to avoid the argparse clash.

**Honesty note (design-critical):** every composite carries a `confidence_label` that
states N and downgrades to "insufficient history — directional only" below N=3; the
dashboard and CLI surface that label verbatim. No output presents a fabricated confidence
percentage. This is enforced in `composite` (Task 4) and rendered in Task 7.
```
