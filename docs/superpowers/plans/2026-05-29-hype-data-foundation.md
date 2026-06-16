# HYPE Data Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python service that continuously captures every guaranteed Hyperliquid fact about the HYPE perpetual into a local SQLite store, with a live dashboard to watch and verify it.

**Architecture:** Two decoupled units sharing one SQLite file (WAL mode). A **collector daemon** backfills history then streams live data via WebSocket + polls REST context; a **read-only FastAPI server** serves a live dashboard over SSE. Pure parsing/gap/verify logic is isolated into small testable modules.

**Tech Stack:** Python 3.12, `uv`, `sqlite3` (stdlib), `httpx` (REST + MockTransport for tests), `websockets`, `fastapi`, `uvicorn`, `pytest`.

> **Git note (per user):** "Add to git later." Do **not** commit per-task. Each task ends at "run tests, green". A single final commit task is gated on explicit user approval.

---

## File Structure

```
glory-hype/
  requirements.txt
  glory_hype/
    __init__.py
    config.py          # API URLs, coin, intervals, large-trade threshold
    parsers.py         # pure: parse_candle, parse_asset_ctx, parse_trade, is_large_trade
    db.py              # SQLite schema + insert (upsert) + latest-row queries
    gaps.py            # pure: find_candle_gaps
    hl_rest.py         # sync httpx: meta_and_asset_ctxs(), candle_snapshot()
    hl_ws.py           # async: subscribe msgs + message router
    collector.py       # daemon: backfill + ws ingest + rest poller + gap heal
    server.py          # FastAPI read API + SSE + serves dashboard
    static/index.html  # dashboard page
    verify.py          # diff stored rows vs live API
    __main__.py        # CLI: collect | serve | verify
  tests/
    test_parsers.py
    test_db.py
    test_gaps.py
    test_rest.py
    test_ws.py
    test_verify.py
    test_server.py
```

Each module has one responsibility. Network code (`hl_rest`, `hl_ws`) is thin; all logic that can be unit-tested without a network lives in `parsers`, `gaps`, `db`, `verify`.

---

### Task 1: Project scaffold

**Files:**
- Create: `glory-hype/requirements.txt`
- Create: `glory-hype/glory_hype/__init__.py`
- Create: `glory-hype/glory_hype/config.py`
- Test: `glory-hype/tests/test_config.py`

- [ ] **Step 1: Create requirements.txt**

```
httpx>=0.27
websockets>=13.0
fastapi>=0.115
uvicorn>=0.30
pytest>=8.0
```

- [ ] **Step 2: Create the package init (empty)**

`glory-hype/glory_hype/__init__.py`:

```python
"""Glory HYPE data foundation (v1)."""
```

- [ ] **Step 3: Write config**

`glory-hype/glory_hype/config.py`:

```python
"""Static configuration for the HYPE data foundation."""

INFO_URL = "https://api.hyperliquid.xyz/info"
WS_URL = "wss://api.hyperliquid.xyz/ws"

COIN = "HYPE"

# Intervals backfilled at startup and refreshed by the poller.
INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]

# Interval string -> milliseconds.
INTERVAL_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

# A trade is "large" when notional (px * sz) >= this many USD.
LARGE_TRADE_NTL_USD = 50_000.0

# REST poll cadence (seconds) for market context + candle refresh.
POLL_INTERVAL_SEC = 30

# Default SQLite path (next to the package's working dir).
DB_PATH = "hype.db"

# Max candles to backfill per interval (API cap is 5000).
BACKFILL_LIMIT = 5000
```

- [ ] **Step 4: Write the failing test**

`glory-hype/tests/test_config.py`:

```python
from glory_hype import config


def test_intervals_all_have_ms():
    for iv in config.INTERVALS:
        assert iv in config.INTERVAL_MS
        assert config.INTERVAL_MS[iv] > 0


def test_coin_is_hype():
    assert config.COIN == "HYPE"
```

- [ ] **Step 5: Run tests**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_config.py -v`
Expected: PASS (2 passed)

---

### Task 2: Parsers (pure functions)

**Files:**
- Create: `glory-hype/glory_hype/parsers.py`
- Test: `glory-hype/tests/test_parsers.py`

- [ ] **Step 1: Write the failing test** (shapes are verbatim from the live API)

`glory-hype/tests/test_parsers.py`:

```python
from glory_hype.parsers import (
    parse_candle, parse_asset_ctx, parse_trade, is_large_trade,
)


def test_parse_candle():
    raw = {"t": 1780065720000, "T": 1780065779999, "s": "HYPE", "i": "1m",
           "o": "62.254", "c": "62.019", "h": "62.264", "l": "62.002",
           "v": "25485.75", "n": 720}
    c = parse_candle(raw)
    assert c == {"interval": "1m", "open_ts": 1780065720000, "close_ts": 1780065779999,
                 "o": 62.254, "h": 62.264, "l": 62.002, "c": 62.019,
                 "v": 25485.75, "n": 720}


def test_parse_asset_ctx():
    raw = {"funding": "0.0000125", "openInterest": "21950294.64", "prevDayPx": "56.964",
           "dayNtlVlm": "1048844881.51", "premium": "-0.0000321631", "oraclePx": "62.183",
           "markPx": "62.139", "midPx": "62.167", "impactPxs": ["62.164", "62.181"],
           "dayBaseVlm": "17099798.35"}
    ctx = parse_asset_ctx(raw)
    assert ctx["funding"] == 0.0000125
    assert ctx["open_interest"] == 21950294.64
    assert ctx["mark_px"] == 62.139
    assert ctx["oracle_px"] == 62.183
    assert ctx["mid_px"] == 62.167
    assert ctx["prev_day_px"] == 56.964
    assert ctx["day_ntl_vlm"] == 1048844881.51
    assert ctx["premium"] == -0.0000321631


def test_parse_trade():
    raw = {"coin": "HYPE", "side": "B", "px": "62.021", "sz": "161.23",
           "time": 1780065772043, "hash": "0xabc", "tid": 694120022159565,
           "users": ["0xaaa", "0xbbb"]}
    t = parse_trade(raw)
    assert t == {"ts": 1780065772043, "px": 62.021, "sz": 161.23,
                 "side": "B", "tid": 694120022159565,
                 "ntl": 62.021 * 161.23, "is_large": False}


def test_is_large_trade_threshold():
    assert is_large_trade(62.0, 1000.0) is True      # 62,000 >= 50,000
    assert is_large_trade(62.0, 100.0) is False       # 6,200 < 50,000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_parsers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'glory_hype.parsers'`

- [ ] **Step 3: Write the implementation**

`glory-hype/glory_hype/parsers.py`:

```python
"""Pure parsers turning raw Hyperliquid JSON into typed dicts. No I/O."""

from glory_hype.config import LARGE_TRADE_NTL_USD


def is_large_trade(px: float, sz: float) -> bool:
    return px * sz >= LARGE_TRADE_NTL_USD


def parse_candle(raw: dict) -> dict:
    """Raw candle (REST candleSnapshot item or WS candle.data) -> typed dict."""
    return {
        "interval": raw["i"],
        "open_ts": int(raw["t"]),
        "close_ts": int(raw["T"]),
        "o": float(raw["o"]),
        "h": float(raw["h"]),
        "l": float(raw["l"]),
        "c": float(raw["c"]),
        "v": float(raw["v"]),
        "n": int(raw["n"]),
    }


def parse_asset_ctx(raw: dict) -> dict:
    """Asset context (REST metaAndAssetCtxs[1][i] or WS activeAssetCtx.data.ctx)."""
    return {
        "funding": float(raw["funding"]),
        "open_interest": float(raw["openInterest"]),
        "mark_px": float(raw["markPx"]),
        "oracle_px": float(raw["oraclePx"]),
        "mid_px": float(raw["midPx"]),
        "premium": float(raw["premium"]),
        "prev_day_px": float(raw["prevDayPx"]),
        "day_ntl_vlm": float(raw["dayNtlVlm"]),
    }


def parse_trade(raw: dict) -> dict:
    """Raw WS trade -> typed dict with notional and large flag."""
    px = float(raw["px"])
    sz = float(raw["sz"])
    return {
        "ts": int(raw["time"]),
        "px": px,
        "sz": sz,
        "side": raw["side"],
        "tid": int(raw["tid"]),
        "ntl": px * sz,
        "is_large": is_large_trade(px, sz),
    }
```

- [ ] **Step 4: Run tests**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_parsers.py -v`
Expected: PASS (4 passed)

---

### Task 3: SQLite store

**Files:**
- Create: `glory-hype/glory_hype/db.py`
- Test: `glory-hype/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_db.py`:

```python
from glory_hype.db import Store


def make_store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_insert_and_get_latest_candle(tmp_path):
    s = make_store(tmp_path)
    c = {"interval": "1m", "open_ts": 1000, "close_ts": 1059, "o": 1.0, "h": 2.0,
         "l": 0.5, "c": 1.5, "v": 10.0, "n": 3}
    s.insert_candle(c)
    assert s.latest_candle("1m")["close"] == 1.5


def test_candle_upsert_on_same_open_ts(tmp_path):
    s = make_store(tmp_path)
    base = {"interval": "1m", "open_ts": 1000, "close_ts": 1059, "o": 1.0, "h": 2.0,
            "l": 0.5, "c": 1.5, "v": 10.0, "n": 3}
    s.insert_candle(base)
    s.insert_candle({**base, "c": 1.9, "v": 12.0, "n": 5})  # same open_ts, updated
    rows = s.candle_open_timestamps("1m")
    assert rows == [1000]                       # not duplicated
    assert s.latest_candle("1m")["close"] == 1.9  # overwritten


def test_insert_ctx_and_trade_and_book(tmp_path):
    s = make_store(tmp_path)
    s.insert_ctx({"funding": 0.0001, "open_interest": 100.0, "mark_px": 62.1,
                  "oracle_px": 62.2, "mid_px": 62.15, "premium": -0.0001,
                  "prev_day_px": 56.9, "day_ntl_vlm": 1000.0}, ts=2000)
    assert s.latest_ctx()["mark_px"] == 62.1

    s.insert_trade({"ts": 3000, "px": 62.0, "sz": 1000.0, "side": "B",
                    "tid": 99, "ntl": 62000.0, "is_large": True})
    assert s.recent_large_trades(limit=10)[0]["tid"] == 99

    s.insert_book(ts=4000, bids=[{"px": 1, "sz": 2, "n": 1}],
                  asks=[{"px": 2, "sz": 3, "n": 1}])
    assert s.latest_book()["ts"] == 4000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'glory_hype.db'`

- [ ] **Step 3: Write the implementation**

`glory-hype/glory_hype/db.py`:

```python
"""SQLite store for HYPE market data. WAL mode so the read-only server can
query concurrently while the collector writes."""

import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    interval TEXT NOT NULL,
    open_ts  INTEGER NOT NULL,
    close_ts INTEGER NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL, n INTEGER,
    PRIMARY KEY (interval, open_ts)
);
CREATE TABLE IF NOT EXISTS market_ctx (
    ts INTEGER PRIMARY KEY,
    funding REAL, open_interest REAL, mark_px REAL, oracle_px REAL,
    mid_px REAL, premium REAL, prev_day_px REAL, day_ntl_vlm REAL
);
CREATE TABLE IF NOT EXISTS trades (
    tid INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL, px REAL, sz REAL, side TEXT, ntl REAL,
    is_large INTEGER
);
CREATE TABLE IF NOT EXISTS book_snapshots (
    ts INTEGER PRIMARY KEY,
    bids_json TEXT, asks_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts);
CREATE INDEX IF NOT EXISTS idx_trades_large ON trades(is_large, ts);
"""


class Store:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def insert_candle(self, c: dict) -> None:
        self.conn.execute(
            """INSERT INTO candles (interval, open_ts, close_ts, o, h, l, c, v, n)
               VALUES (:interval, :open_ts, :close_ts, :o, :h, :l, :c, :v, :n)
               ON CONFLICT(interval, open_ts) DO UPDATE SET
                 close_ts=excluded.close_ts, o=excluded.o, h=excluded.h,
                 l=excluded.l, c=excluded.c, v=excluded.v, n=excluded.n""",
            c,
        )
        self.conn.commit()

    def insert_ctx(self, ctx: dict, ts: int) -> None:
        row = {**ctx, "ts": ts}
        self.conn.execute(
            """INSERT OR REPLACE INTO market_ctx
               (ts, funding, open_interest, mark_px, oracle_px, mid_px, premium,
                prev_day_px, day_ntl_vlm)
               VALUES (:ts, :funding, :open_interest, :mark_px, :oracle_px, :mid_px,
                       :premium, :prev_day_px, :day_ntl_vlm)""",
            row,
        )
        self.conn.commit()

    def insert_trade(self, t: dict) -> None:
        self.conn.execute(
            """INSERT OR IGNORE INTO trades (tid, ts, px, sz, side, ntl, is_large)
               VALUES (:tid, :ts, :px, :sz, :side, :ntl, :is_large)""",
            {**t, "is_large": 1 if t["is_large"] else 0},
        )
        self.conn.commit()

    def insert_book(self, ts: int, bids: list, asks: list) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO book_snapshots (ts, bids_json, asks_json) VALUES (?,?,?)",
            (ts, json.dumps(bids), json.dumps(asks)),
        )
        self.conn.commit()

    # --- reads ---
    def latest_candle(self, interval: str):
        r = self.conn.execute(
            "SELECT * FROM candles WHERE interval=? ORDER BY open_ts DESC LIMIT 1",
            (interval,),
        ).fetchone()
        if r is None:
            return None
        return {"open_ts": r["open_ts"], "open": r["o"], "high": r["h"],
                "low": r["l"], "close": r["c"], "volume": r["v"], "trades": r["n"]}

    def candle_open_timestamps(self, interval: str) -> list:
        rows = self.conn.execute(
            "SELECT open_ts FROM candles WHERE interval=? ORDER BY open_ts", (interval,)
        ).fetchall()
        return [row["open_ts"] for row in rows]

    def latest_ctx(self):
        r = self.conn.execute(
            "SELECT * FROM market_ctx ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        return dict(r) if r else None

    def recent_large_trades(self, limit: int = 20) -> list:
        rows = self.conn.execute(
            "SELECT * FROM trades WHERE is_large=1 ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def latest_book(self):
        r = self.conn.execute(
            "SELECT * FROM book_snapshots ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        return dict(r) if r else None

    def recent_candles(self, interval: str, limit: int = 200) -> list:
        rows = self.conn.execute(
            "SELECT * FROM candles WHERE interval=? ORDER BY open_ts DESC LIMIT ?",
            (interval, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
```

- [ ] **Step 4: Run tests**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_db.py -v`
Expected: PASS (3 passed)

---

### Task 4: Candle gap detection (pure)

**Files:**
- Create: `glory-hype/glory_hype/gaps.py`
- Test: `glory-hype/tests/test_gaps.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_gaps.py`:

```python
from glory_hype.gaps import find_candle_gaps


def test_no_gaps():
    ts = [1000, 1060_000 + 1000 - 60000]  # contiguous handled below
    assert find_candle_gaps([0, 60000, 120000], 60000) == []


def test_one_missing_candle():
    # missing 60000 between 0 and 120000
    assert find_candle_gaps([0, 120000], 60000) == [60000]


def test_multiple_missing():
    assert find_candle_gaps([0, 240000], 60000) == [60000, 120000, 180000]


def test_empty_and_single():
    assert find_candle_gaps([], 60000) == []
    assert find_candle_gaps([1000], 60000) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_gaps.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'glory_hype.gaps'`

- [ ] **Step 3: Write the implementation**

`glory-hype/glory_hype/gaps.py`:

```python
"""Pure candle-gap detection over a sorted list of open timestamps."""


def find_candle_gaps(open_ts: list, interval_ms: int) -> list:
    """Return the open timestamps that SHOULD exist between the first and last
    given timestamps but are missing. Assumes input is sorted ascending."""
    if len(open_ts) < 2:
        return []
    present = set(open_ts)
    missing = []
    t = open_ts[0] + interval_ms
    last = open_ts[-1]
    while t < last:
        if t not in present:
            missing.append(t)
        t += interval_ms
    return missing
```

- [ ] **Step 4: Run tests**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_gaps.py -v`
Expected: PASS (4 passed)

---

### Task 5: REST client

**Files:**
- Create: `glory-hype/glory_hype/hl_rest.py`
- Test: `glory-hype/tests/test_rest.py`

- [ ] **Step 1: Write the failing test** (uses `httpx.MockTransport`, no network)

`glory-hype/tests/test_rest.py`:

```python
import json
import httpx
from glory_hype.hl_rest import RestClient


def _client(handler):
    transport = httpx.MockTransport(handler)
    return RestClient(http=httpx.Client(transport=transport))


def test_meta_and_asset_ctxs_extracts_hype():
    def handler(request):
        body = json.loads(request.content)
        assert body == {"type": "metaAndAssetCtxs"}
        payload = [
            {"universe": [{"name": "BTC"}, {"name": "HYPE"}]},
            [{"markPx": "1"}, {"funding": "0.0000125", "openInterest": "10",
                               "prevDayPx": "56", "dayNtlVlm": "1", "premium": "0",
                               "oraclePx": "62.1", "markPx": "62.0", "midPx": "62.05"}],
        ]
        return httpx.Response(200, json=payload)
    ctx = _client(handler).asset_ctx("HYPE")
    assert ctx["mark_px"] == 62.0


def test_candle_snapshot_parses_list():
    def handler(request):
        body = json.loads(request.content)
        assert body["type"] == "candleSnapshot"
        assert body["req"]["coin"] == "HYPE"
        return httpx.Response(200, json=[
            {"t": 1000, "T": 1059, "s": "HYPE", "i": "1m", "o": "1", "c": "2",
             "h": "3", "l": "0.5", "v": "9", "n": 4}])
    candles = _client(handler).candle_snapshot("HYPE", "1m", 0, 60000)
    assert len(candles) == 1
    assert candles[0]["c"] == 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_rest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'glory_hype.hl_rest'`

- [ ] **Step 3: Write the implementation**

`glory-hype/glory_hype/hl_rest.py`:

```python
"""Synchronous Hyperliquid REST (info) client. Called from the collector via
asyncio.to_thread so the event loop never blocks."""

import httpx

from glory_hype.config import INFO_URL
from glory_hype.parsers import parse_asset_ctx, parse_candle


class RestClient:
    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(timeout=20.0)

    def _post(self, body: dict):
        r = self.http.post(INFO_URL, json=body)
        r.raise_for_status()
        return r.json()

    def asset_ctx(self, coin: str) -> dict:
        meta, ctxs = self._post({"type": "metaAndAssetCtxs"})
        idx = next(i for i, u in enumerate(meta["universe"]) if u["name"] == coin)
        return parse_asset_ctx(ctxs[idx])

    def candle_snapshot(self, coin: str, interval: str,
                        start_ms: int, end_ms: int) -> list:
        raw = self._post({"type": "candleSnapshot", "req": {
            "coin": coin, "interval": interval,
            "startTime": start_ms, "endTime": end_ms}})
        return [parse_candle(c) for c in raw]
```

- [ ] **Step 4: Run tests**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_rest.py -v`
Expected: PASS (2 passed)

---

### Task 6: WebSocket helpers (subscribe messages + router)

**Files:**
- Create: `glory-hype/glory_hype/hl_ws.py`
- Test: `glory-hype/tests/test_ws.py`

The router is a pure function mapping a raw WS message to `(kind, payload)` writes, so it is unit-testable without a socket. The actual connect/recv loop lives in the collector.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_ws.py`:

```python
from glory_hype.hl_ws import subscribe_messages, route_message


def test_subscribe_messages_cover_all_channels():
    msgs = subscribe_messages("HYPE")
    types = {m["subscription"]["type"] for m in msgs}
    assert types == {"candle", "trades", "l2Book", "activeAssetCtx"}
    assert all(m["method"] == "subscribe" for m in msgs)
    candle = next(m for m in msgs if m["subscription"]["type"] == "candle")
    assert candle["subscription"]["interval"] == "1m"


def test_route_candle():
    msg = {"channel": "candle", "data": {"t": 1000, "T": 1059, "s": "HYPE", "i": "1m",
           "o": "1", "c": "2", "h": "3", "l": "0.5", "v": "9", "n": 4}}
    kind, items = route_message(msg)
    assert kind == "candle"
    assert items[0]["c"] == 2.0


def test_route_trades_returns_list():
    msg = {"channel": "trades", "data": [
        {"coin": "HYPE", "side": "B", "px": "62.0", "sz": "1000", "time": 5,
         "hash": "0x", "tid": 7, "users": []}]}
    kind, items = route_message(msg)
    assert kind == "trade"
    assert items[0]["is_large"] is True


def test_route_book():
    msg = {"channel": "l2Book", "data": {"coin": "HYPE", "time": 9,
           "levels": [[{"px": "1", "sz": "2", "n": 1}], [{"px": "2", "sz": "3", "n": 1}]]}}
    kind, payload = route_message(msg)
    assert kind == "book"
    assert payload["ts"] == 9
    assert payload["bids"][0]["px"] == "1"


def test_route_ctx():
    msg = {"channel": "activeAssetCtx", "data": {"coin": "HYPE", "ctx": {
        "funding": "0.0001", "openInterest": "10", "prevDayPx": "56", "dayNtlVlm": "1",
        "premium": "0", "oraclePx": "62.1", "markPx": "62.0", "midPx": "62.05"}}}
    kind, payload = route_message(msg)
    assert kind == "ctx"
    assert payload["mark_px"] == 62.0


def test_route_ignores_subscription_response():
    assert route_message({"channel": "subscriptionResponse", "data": {}}) == ("ignore", None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_ws.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'glory_hype.hl_ws'`

- [ ] **Step 3: Write the implementation**

`glory-hype/glory_hype/hl_ws.py`:

```python
"""Hyperliquid WebSocket helpers: build subscription messages and route
incoming frames into typed writes. Pure (no socket) for testability."""

from glory_hype.parsers import parse_asset_ctx, parse_candle, parse_trade


def subscribe_messages(coin: str) -> list:
    return [
        {"method": "subscribe", "subscription": {"type": "candle", "coin": coin,
                                                 "interval": "1m"}},
        {"method": "subscribe", "subscription": {"type": "trades", "coin": coin}},
        {"method": "subscribe", "subscription": {"type": "l2Book", "coin": coin}},
        {"method": "subscribe", "subscription": {"type": "activeAssetCtx", "coin": coin}},
    ]


def route_message(msg: dict):
    """Return (kind, payload). kind in {candle, trade, book, ctx, ignore}.
    For candle/trade, payload is a list of typed dicts; for book/ctx a dict."""
    channel = msg.get("channel")
    data = msg.get("data")
    if channel == "candle":
        return "candle", [parse_candle(data)]
    if channel == "trades":
        return "trade", [parse_trade(t) for t in data]
    if channel == "l2Book":
        return "book", {"ts": data["time"], "bids": data["levels"][0],
                        "asks": data["levels"][1]}
    if channel == "activeAssetCtx":
        return "ctx", parse_asset_ctx(data["ctx"])
    return "ignore", None
```

- [ ] **Step 4: Run tests**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_ws.py -v`
Expected: PASS (6 passed)

---

### Task 7: Collector daemon

**Files:**
- Create: `glory-hype/glory_hype/collector.py`
- Test: `glory-hype/tests/test_collector.py`

The collector composes the tested pieces. We unit-test the two pure-ish orchestration helpers (`backfill_interval`, `apply_ws_message`) with a real `Store` and a fake REST client; the live connect loop is exercised by the end-to-end smoke (Task 11).

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_collector.py`:

```python
from glory_hype.db import Store
from glory_hype.collector import Collector


class FakeRest:
    def candle_snapshot(self, coin, interval, start_ms, end_ms):
        return [{"interval": interval, "open_ts": 0, "close_ts": 59, "o": 1.0,
                 "h": 2.0, "l": 0.5, "c": 1.5, "v": 9.0, "n": 4}]

    def asset_ctx(self, coin):
        return {"funding": 0.0001, "open_interest": 10.0, "mark_px": 62.0,
                "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                "prev_day_px": 56.0, "day_ntl_vlm": 1.0}


def make(tmp_path):
    store = Store(str(tmp_path / "c.db"))
    return Collector(store=store, rest=FakeRest()), store


def test_backfill_writes_candles(tmp_path):
    col, store = make(tmp_path)
    col.backfill_interval("1m")
    assert store.latest_candle("1m")["close"] == 1.5


def test_poll_ctx_writes_latest(tmp_path):
    col, store = make(tmp_path)
    col.poll_once(now_ms=1234)
    assert store.latest_ctx()["mark_px"] == 62.0


def test_apply_ws_candle_message(tmp_path):
    col, store = make(tmp_path)
    col.apply_ws_message({"channel": "candle", "data": {
        "t": 1000, "T": 1059, "s": "HYPE", "i": "1m", "o": "1", "c": "2",
        "h": "3", "l": "0.5", "v": "9", "n": 4}})
    assert store.latest_candle("1m")["close"] == 2.0


def test_apply_ws_large_trade_message(tmp_path):
    col, store = make(tmp_path)
    col.apply_ws_message({"channel": "trades", "data": [
        {"coin": "HYPE", "side": "B", "px": "62.0", "sz": "1000", "time": 5,
         "hash": "0x", "tid": 7, "users": []}]})
    assert store.recent_large_trades()[0]["tid"] == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_collector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'glory_hype.collector'`

- [ ] **Step 3: Write the implementation**

`glory-hype/glory_hype/collector.py`:

```python
"""Collector daemon: backfill history, stream live WS data, poll REST context,
and self-heal candle gaps. Composes the tested parser/db/ws/rest units."""

import asyncio
import json
import time

import websockets

from glory_hype import config
from glory_hype.db import Store
from glory_hype.gaps import find_candle_gaps
from glory_hype.hl_rest import RestClient
from glory_hype.hl_ws import route_message, subscribe_messages


class Collector:
    def __init__(self, store: Store, rest=None):
        self.store = store
        self.rest = rest or RestClient()

    # --- composable units (unit-tested) ---
    def backfill_interval(self, interval: str) -> None:
        now = int(time.time() * 1000)
        span = config.INTERVAL_MS[interval] * config.BACKFILL_LIMIT
        candles = self.rest.candle_snapshot(config.COIN, interval, now - span, now)
        for c in candles:
            self.store.insert_candle(c)

    def poll_once(self, now_ms: int) -> None:
        ctx = self.rest.asset_ctx(config.COIN)
        self.store.insert_ctx(ctx, ts=now_ms)

    def heal_gaps(self, interval: str) -> int:
        ts = self.store.candle_open_timestamps(interval)
        missing = find_candle_gaps(ts, config.INTERVAL_MS[interval])
        if not missing:
            return 0
        candles = self.rest.candle_snapshot(
            config.COIN, interval, missing[0], missing[-1] + config.INTERVAL_MS[interval])
        for c in candles:
            self.store.insert_candle(c)
        return len(missing)

    def apply_ws_message(self, msg: dict) -> None:
        kind, payload = route_message(msg)
        if kind == "candle":
            for c in payload:
                self.store.insert_candle(c)
        elif kind == "trade":
            for t in payload:
                self.store.insert_trade(t)
        elif kind == "book":
            self.store.insert_book(payload["ts"], payload["bids"], payload["asks"])
        elif kind == "ctx":
            self.store.insert_ctx(payload, ts=int(time.time() * 1000))

    # --- async loops (exercised by the live smoke) ---
    async def _poll_loop(self):
        while True:
            try:
                await asyncio.to_thread(self.poll_once, int(time.time() * 1000))
                for iv in config.INTERVALS:
                    await asyncio.to_thread(self.backfill_recent, iv)
                    await asyncio.to_thread(self.heal_gaps, iv)
            except Exception as e:  # keep the daemon alive
                print(f"[poll] error: {e}")
            await asyncio.sleep(config.POLL_INTERVAL_SEC)

    def backfill_recent(self, interval: str) -> None:
        """Refresh the last few candles of an interval to keep them current."""
        now = int(time.time() * 1000)
        span = config.INTERVAL_MS[interval] * 5
        for c in self.rest.candle_snapshot(config.COIN, interval, now - span, now):
            self.store.insert_candle(c)

    async def _ws_loop(self):
        while True:
            try:
                async with websockets.connect(config.WS_URL, open_timeout=15) as ws:
                    for m in subscribe_messages(config.COIN):
                        await ws.send(json.dumps(m))
                    print("[ws] connected + subscribed")
                    async for raw in ws:
                        self.apply_ws_message(json.loads(raw))
            except Exception as e:
                print(f"[ws] disconnected: {e}; reconnecting in 3s")
                await asyncio.sleep(3)

    async def run(self):
        # backfill once, then run poller + ws concurrently forever
        for iv in config.INTERVALS:
            await asyncio.to_thread(self.backfill_interval, iv)
        print("[collector] backfill complete; going live")
        await asyncio.gather(self._poll_loop(), self._ws_loop())
```

- [ ] **Step 4: Run tests**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_collector.py -v`
Expected: PASS (4 passed)

---

### Task 8: Verify command

**Files:**
- Create: `glory-hype/glory_hype/verify.py`
- Test: `glory-hype/tests/test_verify.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_verify.py`:

```python
from glory_hype.db import Store
from glory_hype.verify import verify_ctx


class FakeRest:
    def __init__(self, mark):
        self._mark = mark

    def asset_ctx(self, coin):
        return {"funding": 0.0001, "open_interest": 10.0, "mark_px": self._mark,
                "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                "prev_day_px": 56.0, "day_ntl_vlm": 1.0}


def test_verify_passes_within_tolerance(tmp_path):
    s = Store(str(tmp_path / "v.db"))
    s.insert_ctx({"funding": 0.0001, "open_interest": 10.0, "mark_px": 62.00,
                  "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                  "prev_day_px": 56.0, "day_ntl_vlm": 1.0}, ts=1)
    ok, report = verify_ctx(s, FakeRest(62.01), tol_pct=0.5)
    assert ok is True


def test_verify_fails_outside_tolerance(tmp_path):
    s = Store(str(tmp_path / "v2.db"))
    s.insert_ctx({"funding": 0.0001, "open_interest": 10.0, "mark_px": 62.00,
                  "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                  "prev_day_px": 56.0, "day_ntl_vlm": 1.0}, ts=1)
    ok, report = verify_ctx(s, FakeRest(70.0), tol_pct=0.5)
    assert ok is False
    assert "mark_px" in report


def test_verify_no_data(tmp_path):
    s = Store(str(tmp_path / "v3.db"))
    ok, report = verify_ctx(s, FakeRest(62.0), tol_pct=0.5)
    assert ok is False
    assert "no stored" in report.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_verify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'glory_hype.verify'`

- [ ] **Step 3: Write the implementation**

`glory-hype/glory_hype/verify.py`:

```python
"""Verify stored market context matches the live exchange within tolerance."""

from glory_hype.config import COIN

_FIELDS = ["mark_px", "oracle_px", "mid_px", "open_interest"]


def verify_ctx(store, rest, tol_pct: float = 0.5):
    """Compare latest stored ctx vs live. Returns (ok, human_report)."""
    stored = store.latest_ctx()
    if stored is None:
        return False, "FAIL: no stored market_ctx rows yet."
    live = rest.asset_ctx(COIN)
    lines = []
    ok = True
    for f in _FIELDS:
        s, l = stored[f], live[f]
        denom = abs(l) if l else 1.0
        diff_pct = abs(s - l) / denom * 100
        flag = "OK" if diff_pct <= tol_pct else "MISMATCH"
        if diff_pct > tol_pct:
            ok = False
        lines.append(f"  {f}: stored={s} live={l} diff={diff_pct:.3f}% [{flag}]")
    header = "PASS" if ok else "FAIL"
    return ok, header + "\n" + "\n".join(lines)
```

- [ ] **Step 4: Run tests**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_verify.py -v`
Expected: PASS (3 passed)

---

### Task 9: Read API + SSE server

**Files:**
- Create: `glory-hype/glory_hype/server.py`
- Test: `glory-hype/tests/test_server.py`

- [ ] **Step 1: Write the failing test** (FastAPI `TestClient`, seeded DB, no network)

`glory-hype/tests/test_server.py`:

```python
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def seeded(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.insert_ctx({"funding": 0.0001, "open_interest": 10.0, "mark_px": 62.0,
                  "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                  "prev_day_px": 56.0, "day_ntl_vlm": 1.0}, ts=1000)
    s.insert_candle({"interval": "1m", "open_ts": 0, "close_ts": 59, "o": 1.0,
                     "h": 2.0, "l": 0.5, "c": 1.5, "v": 9.0, "n": 4})
    s.insert_trade({"ts": 2000, "px": 62.0, "sz": 1000.0, "side": "B", "tid": 7,
                    "ntl": 62000.0, "is_large": True})
    return s


def test_snapshot_endpoint(tmp_path):
    app = create_app(seeded(tmp_path))
    client = TestClient(app)
    r = client.get("/api/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert body["ctx"]["mark_px"] == 62.0
    assert body["large_trades"][0]["tid"] == 7
    assert body["candles_1m"][-1]["c"] == 1.5


def test_dashboard_served(tmp_path):
    app = create_app(seeded(tmp_path))
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "HYPE" in r.text


def test_health_reports_freshness(tmp_path):
    app = create_app(seeded(tmp_path))
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "ctx_ts" in r.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'glory_hype.server'`

- [ ] **Step 3: Write the implementation**

`glory-hype/glory_hype/server.py`:

```python
"""Read-only FastAPI server: snapshot JSON, health, SSE stream, dashboard page."""

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from glory_hype.db import Store

_STATIC = Path(__file__).parent / "static"


def _snapshot(store: Store) -> dict:
    return {
        "ctx": store.latest_ctx(),
        "large_trades": store.recent_large_trades(20),
        "candles_1m": store.recent_candles("1m", 200),
        "latest_book": store.latest_book(),
    }


def create_app(store: Store) -> FastAPI:
    app = FastAPI(title="Glory HYPE Data Foundation")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (_STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/api/snapshot")
    def snapshot():
        return _snapshot(store)

    @app.get("/api/health")
    def health():
        ctx = store.latest_ctx()
        return {"ctx_ts": ctx["ts"] if ctx else None,
                "candles_1m": len(store.candle_open_timestamps("1m"))}

    @app.get("/api/stream")
    async def stream():
        async def gen():
            while True:
                yield f"data: {json.dumps(_snapshot(store))}\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(gen(), media_type="text/event-stream")

    return app
```

- [ ] **Step 4: Run tests**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_server.py -v`
Expected: FAIL — `index.html` does not exist yet (raises on `/`). The two API tests pass; `test_dashboard_served` fails. This is expected; the page is created in Task 10.

---

### Task 10: Dashboard page

**Files:**
- Create: `glory-hype/glory_hype/static/index.html`

No unit test (it's static markup); verified by `test_dashboard_served` (Task 9) going green and by manual inspection.

- [ ] **Step 1: Create the dashboard**

`glory-hype/glory_hype/static/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Glory HYPE — Data Foundation</title>
<style>
  body { background:#0b0e11; color:#e6e6e6; font:14px/1.5 system-ui, sans-serif; margin:0; padding:24px; }
  h1 { font-size:18px; margin:0 0 16px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }
  .card { background:#151a21; border:1px solid #232b36; border-radius:10px; padding:14px; }
  .label { color:#8b97a7; font-size:11px; text-transform:uppercase; letter-spacing:.05em; }
  .val { font-size:20px; margin-top:4px; }
  .pos { color:#26de81; } .neg { color:#fc5c65; }
  table { width:100%; border-collapse:collapse; margin-top:8px; font-size:12px; }
  td,th { text-align:left; padding:4px 8px; border-bottom:1px solid #232b36; }
  #health { margin:16px 0; font-size:12px; }
  .ok { color:#26de81; } .stale { color:#fc5c65; }
</style>
</head>
<body>
  <h1>Glory HYPE — Data Foundation <span id="health"></span></h1>
  <div class="grid" id="cards"></div>
  <h2 style="font-size:14px;margin-top:24px;">Recent large trades</h2>
  <table id="trades"><thead><tr><th>Time</th><th>Side</th><th>Px</th><th>Size</th><th>Notional</th></tr></thead><tbody></tbody></table>

<script>
function fmt(n, d=4){ return n==null ? "—" : Number(n).toLocaleString(undefined,{maximumFractionDigits:d}); }
function ageStr(ms){ const s=Math.round((Date.now()-ms)/1000); return s+"s ago"; }

function render(snap){
  const ctx = snap.ctx || {};
  const cards = [
    ["Mark price", fmt(ctx.mark_px)],
    ["Oracle price", fmt(ctx.oracle_px)],
    ["Mid price", fmt(ctx.mid_px)],
    ["Funding", (ctx.funding!=null ? (ctx.funding*100).toFixed(5)+"%" : "—")],
    ["Open interest", fmt(ctx.open_interest,0)],
    ["24h notional vol", fmt(ctx.day_ntl_vlm,0)],
    ["Prev day px", fmt(ctx.prev_day_px)],
    ["Premium", fmt(ctx.premium,6)],
  ];
  document.getElementById("cards").innerHTML = cards.map(
    ([l,v]) => `<div class="card"><div class="label">${l}</div><div class="val">${v}</div></div>`
  ).join("");

  const tb = document.querySelector("#trades tbody");
  tb.innerHTML = (snap.large_trades||[]).map(t =>
    `<tr><td>${new Date(t.ts).toLocaleTimeString()}</td>
         <td class="${t.side==='B'?'pos':'neg'}">${t.side==='B'?'BUY':'SELL'}</td>
         <td>${fmt(t.px)}</td><td>${fmt(t.sz,2)}</td><td>$${fmt(t.ntl,0)}</td></tr>`
  ).join("");

  const h = document.getElementById("health");
  if (ctx.ts){ const fresh = (Date.now()-ctx.ts) < 90000;
    h.innerHTML = `<span class="${fresh?'ok':'stale'}">● ${fresh?'live':'STALE'} (ctx ${ageStr(ctx.ts)})</span>`; }
}

const es = new EventSource("/api/stream");
es.onmessage = (e) => render(JSON.parse(e.data));
fetch("/api/snapshot").then(r=>r.json()).then(render);
</script>
</body>
</html>
```

- [ ] **Step 2: Run the server tests (now fully green)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_server.py -v`
Expected: PASS (3 passed)

- [ ] **Step 3: Run the full unit suite**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets pytest -v`
Expected: PASS (all tests across all modules)

---

### Task 11: CLI entrypoint + live end-to-end smoke

**Files:**
- Create: `glory-hype/glory_hype/__main__.py`
- Test: `glory-hype/tests/test_smoke_live.py` (network; opt-in)

- [ ] **Step 1: Write the CLI**

`glory-hype/glory_hype/__main__.py`:

```python
"""CLI: python -m glory_hype <collect|serve|verify> [--db PATH] [--port N]"""

import argparse
import asyncio

import uvicorn

from glory_hype import config
from glory_hype.collector import Collector
from glory_hype.db import Store
from glory_hype.hl_rest import RestClient
from glory_hype.server import create_app
from glory_hype.verify import verify_ctx


def main():
    p = argparse.ArgumentParser(prog="glory_hype")
    p.add_argument("cmd", choices=["collect", "serve", "verify"])
    p.add_argument("--db", default=config.DB_PATH)
    p.add_argument("--port", type=int, default=5179)
    args = p.parse_args()

    store = Store(args.db)
    if args.cmd == "collect":
        asyncio.run(Collector(store).run())
    elif args.cmd == "serve":
        uvicorn.run(create_app(store), host="0.0.0.0", port=args.port)
    elif args.cmd == "verify":
        ok, report = verify_ctx(store, RestClient())
        print(report)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the live smoke test** (opt-in via marker; hits the real API briefly)

`glory-hype/tests/test_smoke_live.py`:

```python
import asyncio
import time

import pytest

from glory_hype.collector import Collector
from glory_hype.db import Store

pytestmark = pytest.mark.live


def test_live_backfill_and_poll(tmp_path):
    """Real network: backfill 1m candles + one ctx poll, then assert rows landed."""
    store = Store(str(tmp_path / "live.db"))
    col = Collector(store)
    col.backfill_interval("1m")
    col.poll_once(now_ms=int(time.time() * 1000))
    assert store.latest_candle("1m") is not None
    ctx = store.latest_ctx()
    assert ctx is not None and ctx["mark_px"] > 0


def test_live_ws_receives_messages(tmp_path):
    """Real network: connect WS, ingest ~5s, assert at least one candle row."""
    store = Store(str(tmp_path / "ws.db"))
    col = Collector(store)

    async def run_for(seconds):
        task = asyncio.create_task(col._ws_loop())
        await asyncio.sleep(seconds)
        task.cancel()

    asyncio.run(run_for(8))
    assert store.latest_candle("1m") is not None
```

- [ ] **Step 3: Register the `live` marker**

`glory-hype/pytest.ini`:

```ini
[pytest]
markers =
    live: hits the real Hyperliquid API (opt-in)
addopts = -m "not live"
```

- [ ] **Step 4: Run the offline suite (live excluded by default)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets pytest -v`
Expected: PASS; live tests deselected.

- [ ] **Step 5: Run the live smoke explicitly**

Run: `cd glory-hype && uv run --with pytest --with httpx --with websockets pytest -m live -v`
Expected: PASS (2 passed) — real candle + ctx rows land; WS delivers a candle within 8s.

- [ ] **Step 6: Manual end-to-end check**

```bash
# Terminal A — start the collector daemon
cd glory-hype && uv run --with httpx --with websockets python -m glory_hype collect
# Terminal B — start the dashboard
cd glory-hype && uv run --with fastapi --with uvicorn --with httpx python -m glory_hype serve --port 5179
# Browser: http://localhost:5179  → cards populate, health shows "live", large trades stream in.
# Terminal C — verify stored data matches the live exchange
cd glory-hype && uv run --with httpx python -m glory_hype verify
# Expected: "PASS" with per-field diffs under tolerance.
```

---

### Task 12: Commit (GATED — only after user approval)

> Per the user's "add to git later", do not run this until the user explicitly says to commit.

- [ ] **Step 1: Stage and commit**

```bash
cd E:/Glory
git add glory-hype docs/superpowers/specs/2026-05-29-hype-data-foundation-design.md docs/superpowers/plans/2026-05-29-hype-data-foundation.md
git commit -m "feat(hype): HYPE data foundation v1 — collector daemon + live dashboard

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Guaranteed data (candles, funding, OI, mark/oracle/mid, premium, 24h vol/range, trades, book) → Tasks 2,3,5,6,7 ✓
- Collector daemon (WS stream + REST poll + backfill + gap heal + resilience) → Task 7 ✓
- Read API + dashboard + SSE + freshness indicator → Tasks 9,10 ✓
- SQLite store with the spec's tables → Task 3 ✓ (`candles`, `market_ctx`, `trades`, `book_snapshots`)
- Verification (verify command + freshness + continuity) → Tasks 8,11 ✓
- Roadmap layers (whales/narratives/reader/engine/learning) → explicitly out of v1 scope; not built ✓

**Placeholder scan:** No TBD/TODO; every code step contains complete code; every command has expected output. ✓

**Type consistency:** `Store` method names (`insert_candle`, `insert_ctx`, `insert_trade`, `insert_book`, `latest_candle`, `latest_ctx`, `recent_large_trades`, `latest_book`, `candle_open_timestamps`, `recent_candles`) are used identically across db/collector/server/verify tasks. `route_message` returns `(kind, payload)` consumed the same way in `apply_ws_message`. Parser output dict keys match db insert params. ✓

**Note on Task 9/10 ordering:** Task 9's `test_dashboard_served` intentionally fails until Task 10 creates `index.html`; called out explicitly so the worker isn't surprised.
