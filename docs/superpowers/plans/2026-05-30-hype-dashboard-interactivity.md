# HYPE Dashboard Interactivity (v3.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add drop-to-read chart upload (agent finalizes the read) and a trade calculator (position sizing + PnL + R:R + liquidation + suggestions) to the HYPE dashboard.

**Architecture:** Extends v3. A pure `calc.py` (no I/O) for trade math; a `status` column + pending/finalize flow on `chart_reads` so a dropped chart is queued until the agent reads the saved image; new FastAPI endpoints + dashboard UI. The agent remains the vision engine.

**Tech Stack:** Python 3.12, `uv`, stdlib `sqlite3`, `fastapi`, `python-multipart` (new, for uploads), `pytest`.

> **Git note:** v1+v2 committed (c814cc4f); v3 is built but uncommitted. Do NOT commit per-task. Final commit (Task 8) is gated on explicit user approval and will include v3 + v3.1 together.

Run offline tests with:
`cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart pytest -q`

---

## File Structure

```
glory-hype/
  requirements.txt                 # MODIFY: add python-multipart
  pyproject.toml                   # MODIFY: add python-multipart
  glory_hype/
    calc.py                        # NEW: compute_trade (pure)
    db.py                          # MODIFY: status column + migration + pending/finalize methods
    chart/record.py                # MODIFY: add finalize_chart_read
    server.py                      # MODIFY: /api/calc, /api/chart/upload, /api/chart/pending
    static/index.html              # MODIFY: drop zone, pending queue, calculator form
    __main__.py                    # MODIFY: chart --pending / --finalize
  tests/
    test_calc.py
    test_chart_pending.py
    test_calc_server.py
    test_chart_upload_server.py
```

---

### Task 1: Trade calculator (pure)

**Files:**
- Create: `glory-hype/glory_hype/calc.py`
- Test: `glory-hype/tests/test_calc.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_calc.py`:

```python
import pytest
from glory_hype.calc import compute_trade


def test_margin_mode_long():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 110.0, "sl": 95.0,
                       "direction": "long", "leverage": 10, "margin": 500.0})
    assert r["position_notional"] == 5000.0          # 500 * 10
    assert r["position_coins"] == 50.0               # 5000 / 100
    assert r["margin"] == 500.0
    assert r["pnl_at_tp"] == 500.0                    # 50 * (110-100)
    assert r["pnl_at_sl"] == -250.0                   # 50 * (95-100)
    assert r["roi_tp"] == 1.0                          # 500/500
    assert r["roi_sl"] == -0.5
    assert r["rr"] == 2.0                              # |110-100| / |100-95|
    assert round(r["liq_price"], 2) == 90.0            # 100*(1-1/10)


def test_position_mode_short():
    r = compute_trade({"mode": "position", "entry": 100.0, "tp": 90.0, "sl": 104.0,
                       "direction": "short", "leverage": 5,
                       "position_notional": 5000.0})
    assert r["margin"] == 1000.0                       # 5000/5
    assert r["position_coins"] == 50.0
    assert r["pnl_at_tp"] == 500.0                     # short: 50*(100-90)
    assert r["pnl_at_sl"] == -200.0                    # 50*(100-104)
    assert r["rr"] == 2.5                              # |90-100| / |100-104|
    assert round(r["liq_price"], 2) == 120.0           # 100*(1+1/5)


def test_risk_pct_mode_sizes_to_risk():
    # risk 2% of 10000 = $200 loss at SL; entry-sl distance = 5 -> coins = 40
    r = compute_trade({"mode": "risk_pct", "entry": 100.0, "tp": 115.0, "sl": 95.0,
                       "direction": "long", "leverage": 10,
                       "account": 10000.0, "risk_pct": 0.02})
    assert r["position_coins"] == 40.0                 # 200 / 5
    assert r["position_notional"] == 4000.0            # 40 * 100
    assert r["margin"] == 400.0                         # 4000 / 10
    assert round(r["pnl_at_sl"], 2) == -200.0           # exactly the risk
    assert r["pnl_at_tp"] == 600.0                       # 40 * 15


def test_rr_none_when_no_risk_distance():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 110.0, "sl": 100.0,
                       "direction": "long", "leverage": 2, "margin": 100.0})
    assert r["rr"] is None


def test_suggestion_low_rr():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 102.0, "sl": 95.0,
                       "direction": "long", "leverage": 5, "margin": 100.0})
    assert any("smaller than risk" in s.lower() for s in r["suggestions"])


def test_suggestion_healthy_rr():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 120.0, "sl": 95.0,
                       "direction": "long", "leverage": 5, "margin": 100.0})
    assert any("healthy r:r" in s.lower() for s in r["suggestions"])


def test_suggestion_sl_beyond_liquidation():
    # long, leverage 10 -> liq ~90; sl at 88 is beyond liq
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 130.0, "sl": 88.0,
                       "direction": "long", "leverage": 10, "margin": 100.0})
    assert any("liquidation" in s.lower() for s in r["suggestions"])


def test_suggestion_inverted_tp():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 95.0, "sl": 90.0,
                       "direction": "long", "leverage": 5, "margin": 100.0})
    assert any("wrong side" in s.lower() for s in r["suggestions"])


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        compute_trade({"mode": "margin", "entry": 0, "tp": 1, "sl": 1,
                       "direction": "long", "leverage": 5, "margin": 100.0})
    with pytest.raises(ValueError):
        compute_trade({"mode": "margin", "entry": 100, "tp": 110, "sl": 95,
                       "direction": "long", "leverage": 0.5, "margin": 100.0})
    with pytest.raises(ValueError):
        compute_trade({"mode": "risk_pct", "entry": 100, "tp": 110, "sl": 100,
                       "direction": "long", "leverage": 5,
                       "account": 1000, "risk_pct": 0.02})  # zero risk distance
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_calc.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/calc.py`:

```python
"""Pure trade calculator: position sizing, PnL, R:R, liquidation estimate, tips.

Gross PnL — excludes trading fees and funding (labeled as such in the UI)."""


def _require_positive(name, v):
    if not isinstance(v, (int, float)) or v <= 0:
        raise ValueError(f"{name} must be a positive number")
    return float(v)


def compute_trade(p: dict) -> dict:
    mode = p.get("mode")
    direction = p.get("direction")
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")
    entry = _require_positive("entry", p.get("entry"))
    tp = _require_positive("tp", p.get("tp"))
    sl = _require_positive("sl", p.get("sl"))
    leverage = p.get("leverage")
    if not isinstance(leverage, (int, float)) or leverage < 1:
        raise ValueError("leverage must be >= 1")
    leverage = float(leverage)

    # Resolve position size + margin by mode.
    if mode == "margin":
        margin = _require_positive("margin", p.get("margin"))
        notional = margin * leverage
    elif mode == "position":
        notional = _require_positive("position_notional", p.get("position_notional"))
        margin = notional / leverage
    elif mode == "risk_pct":
        account = _require_positive("account", p.get("account"))
        risk_pct = _require_positive("risk_pct", p.get("risk_pct"))
        risk_dollars = account * risk_pct
        risk_distance = abs(entry - sl)
        if risk_distance == 0:
            raise ValueError("entry and sl must differ for risk_pct sizing")
        coins = risk_dollars / risk_distance
        notional = coins * entry
        margin = notional / leverage
    else:
        raise ValueError("mode must be 'margin', 'position', or 'risk_pct'")

    coins = notional / entry

    def pnl(exit_px):
        if direction == "long":
            return coins * (exit_px - entry)
        return coins * (entry - exit_px)

    pnl_tp = pnl(tp)
    pnl_sl = pnl(sl)
    risk_distance = abs(entry - sl)
    reward_distance = abs(tp - entry)
    rr = round(reward_distance / risk_distance, 4) if risk_distance else None

    if direction == "long":
        liq_price = entry * (1 - 1 / leverage)
    else:
        liq_price = entry * (1 + 1 / leverage)

    suggestions = []
    if rr is not None and rr < 1:
        suggestions.append(f"Reward is smaller than risk (R:R {rr}) — unfavorable.")
    if rr is not None and rr >= 2:
        suggestions.append(f"Healthy R:R ({rr}).")
    if direction == "long" and sl <= liq_price:
        suggestions.append(
            f"⚠️ Stop ({sl}) is at/beyond estimated liquidation "
            f"({round(liq_price, 4)}) — you'd be liquidated first.")
    if direction == "short" and sl >= liq_price:
        suggestions.append(
            f"⚠️ Stop ({sl}) is at/beyond estimated liquidation "
            f"({round(liq_price, 4)}) — you'd be liquidated first.")
    if (direction == "long" and tp <= entry) or (direction == "short" and tp >= entry):
        suggestions.append(f"⚠️ TP is on the wrong side of entry for a {direction}.")
    if (direction == "long" and sl >= entry) or (direction == "short" and sl <= entry):
        suggestions.append(f"⚠️ SL is on the wrong side of entry for a {direction}.")
    if mode == "risk_pct" and p.get("risk_pct", 0) > 0.05:
        suggestions.append("Risking >5% of account on one trade is aggressive.")

    return {
        "position_notional": round(notional, 6),
        "position_coins": round(coins, 6),
        "margin": round(margin, 6),
        "pnl_at_tp": round(pnl_tp, 6),
        "pnl_at_sl": round(pnl_sl, 6),
        "roi_tp": round(pnl_tp / margin, 6) if margin else None,
        "roi_sl": round(pnl_sl / margin, 6) if margin else None,
        "rr": rr,
        "liq_price": round(liq_price, 6),
        "suggestions": suggestions,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_calc.py -v`
Expected: PASS (9 passed)

---

### Task 2: chart_reads status column + pending/finalize Store methods

**Files:**
- Modify: `glory-hype/glory_hype/db.py`
- Test: `glory-hype/tests/test_chart_pending.py`

Context: add a `status` column (default `"read"` so existing v3 inserts/rows are unaffected), a guarded migration for any pre-existing `hype.db`, and three methods. `latest_chart_read` must return the latest **read** (not pending) row.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_chart_pending.py`:

```python
from glory_hype.db import Store


def test_pending_then_finalize(tmp_path):
    s = Store(str(tmp_path / "p.db"))
    s.insert_pending_chart_read(ts=1000, image_path="charts/a.png")
    pend = s.pending_chart_reads()
    assert len(pend) == 1
    assert pend[0]["ts"] == 1000
    assert pend[0]["image_path"] == "charts/a.png"
    # latest_chart_read ignores pending rows
    assert s.latest_chart_read() is None

    s.finalize_chart_read(1000, {"ts": 1000, "timeframe": "1h", "trend": "up",
                                 "current_price": 65.0, "image_path": "charts/a.png",
                                 "support_levels": [64.0]})
    assert s.pending_chart_reads() == []
    latest = s.latest_chart_read()
    assert latest["trend"] == "up"
    assert latest["support_levels"] == [64.0]


def test_existing_read_insert_still_works(tmp_path):
    s = Store(str(tmp_path / "p2.db"))
    s.insert_chart_read({"ts": 5, "timeframe": "1d", "trend": "down",
                         "current_price": 64.0, "image_path": None})
    assert s.latest_chart_read()["ts"] == 5      # status defaults to "read"
    assert s.pending_chart_reads() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chart_pending.py -v`
Expected: FAIL — `insert_pending_chart_read` not defined.

- [ ] **Step 3: Add status to the chart_reads schema + a migration**

In `glory-hype/glory_hype/db.py`, change the `chart_reads` CREATE TABLE in `SCHEMA` to include the column (find the existing block and add the `status` line):

```sql
CREATE TABLE IF NOT EXISTS chart_reads (
    ts INTEGER PRIMARY KEY,
    timeframe TEXT,
    trend TEXT,
    current_price REAL,
    image_path TEXT,
    status TEXT NOT NULL DEFAULT 'read',
    json TEXT NOT NULL
);
```

Then add a migration call in `Store.__init__`, immediately after `self.conn.executescript(SCHEMA)` and before the existing `self.conn.commit()`:

```python
        self._migrate()
```

And add the `_migrate` method to the `Store` class (guarded — safe on fresh and existing DBs):

```python
    def _migrate(self) -> None:
        cols = [r["name"] for r in self.conn.execute(
            "PRAGMA table_info(chart_reads)").fetchall()]
        if "status" not in cols:
            self.conn.execute(
                "ALTER TABLE chart_reads ADD COLUMN status TEXT NOT NULL DEFAULT 'read'")
```

- [ ] **Step 4: Add the Store methods**

Add to the `Store` class in `db.py`. Note `insert_chart_read` already exists; modify it to write `status='read'` explicitly, and update `latest_chart_read` to filter on read status:

```python
    def insert_pending_chart_read(self, ts: int, image_path: str | None) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO chart_reads
                   (ts, timeframe, trend, current_price, image_path, status, json)
                   VALUES (?, 'unknown', 'unknown', NULL, ?, 'pending', ?)""",
                (ts, image_path, json.dumps({"ts": ts, "image_path": image_path,
                                             "status": "pending"})),
            )
            self.conn.commit()

    def pending_chart_reads(self) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT ts, image_path FROM chart_reads WHERE status='pending' "
                "ORDER BY ts DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def finalize_chart_read(self, ts: int, read: dict) -> bool:
        with self._lock:
            cur = self.conn.execute(
                """UPDATE chart_reads SET timeframe=?, trend=?, current_price=?,
                   image_path=?, status='read', json=? WHERE ts=?""",
                (read.get("timeframe"), read.get("trend"), read.get("current_price"),
                 read.get("image_path"), json.dumps(read), ts),
            )
            self.conn.commit()
            return cur.rowcount > 0
```

Modify the existing `insert_chart_read` to set status explicitly (find it and update the column list + values):

```python
    def insert_chart_read(self, read: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO chart_reads
                   (ts, timeframe, trend, current_price, image_path, status, json)
                   VALUES (?,?,?,?,?, 'read', ?)""",
                (read["ts"], read.get("timeframe"), read.get("trend"),
                 read.get("current_price"), read.get("image_path"),
                 json.dumps(read)),
            )
            self.conn.commit()
```

Modify the existing `latest_chart_read` to only return read rows:

```python
    def latest_chart_read(self):
        with self._lock:
            r = self.conn.execute(
                "SELECT json FROM chart_reads WHERE status='read' "
                "ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return json.loads(r["json"]) if r else None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chart_pending.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Run the full suite (no regression to v3 chart tests)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart pytest -q`
Expected: all prior tests still pass (status defaults to 'read').

---

### Task 3: finalize_chart_read in record.py

**Files:**
- Modify: `glory-hype/glory_hype/chart/record.py`
- Test: `glory-hype/tests/test_chart_pending.py` (extend)

Context: a helper that takes the agent's extracted data for a pending ts, parses it defensively (reusing `parse_chart_read`), and updates the row via the Store. Preserves the pending row's image_path if the new data omits it.

- [ ] **Step 1: Add a failing test** (append to `tests/test_chart_pending.py`)

```python
def test_finalize_via_record(tmp_path):
    from glory_hype.chart.record import finalize_chart_read
    s = Store(str(tmp_path / "p3.db"))
    s.insert_pending_chart_read(ts=2000, image_path="charts/b.png")
    read = finalize_chart_read(s, 2000, {"timeframe": "4h", "trend": "down",
                                         "current_price": 64.2})
    assert read.trend == "down"
    assert read.image_path == "charts/b.png"     # preserved from pending row
    assert s.latest_chart_read()["timeframe"] == "4h"
    assert s.pending_chart_reads() == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chart_pending.py::test_finalize_via_record -v`
Expected: FAIL — `finalize_chart_read` not defined.

- [ ] **Step 3: Implement** (add to `glory-hype/glory_hype/chart/record.py`)

Add this import at the top if not present (the file already imports from chartread):

```python
# (parse_chart_read already imported in record.py)
```

Add the function:

```python
def finalize_chart_read(store, ts: int, data: dict):
    """Finalize a pending chart read: parse the agent's extraction and update
    the existing row. Preserves the pending row's image_path if data omits it."""
    image_path = data.get("image_path")
    if image_path is None:
        for row in store.pending_chart_reads():
            if row["ts"] == ts:
                image_path = row["image_path"]
                break
    read = parse_chart_read(data, ts=ts, image_path=image_path)
    store.finalize_chart_read(ts, read.to_dict())
    return read
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chart_pending.py -v`
Expected: PASS (3 passed)

---

### Task 4: /api/calc endpoint + python-multipart dependency

**Files:**
- Modify: `glory-hype/requirements.txt`, `glory-hype/pyproject.toml`
- Modify: `glory-hype/glory_hype/server.py`
- Test: `glory-hype/tests/test_calc_server.py`

- [ ] **Step 1: Add the dependency**

Append `python-multipart>=0.0.9` to `glory-hype/requirements.txt`, and add `"python-multipart>=0.0.9"` to the `dependencies` list in `glory-hype/pyproject.toml`.

- [ ] **Step 2: Write the failing test**

`glory-hype/tests/test_calc_server.py`:

```python
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def client(tmp_path):
    return TestClient(create_app(Store(str(tmp_path / "s.db"))))


def test_calc_endpoint_ok(tmp_path):
    r = client(tmp_path).post("/api/calc", json={
        "mode": "margin", "entry": 100.0, "tp": 110.0, "sl": 95.0,
        "direction": "long", "leverage": 10, "margin": 500.0})
    assert r.status_code == 200
    body = r.json()
    assert body["position_notional"] == 5000.0
    assert body["rr"] == 2.0


def test_calc_endpoint_bad_input_400(tmp_path):
    r = client(tmp_path).post("/api/calc", json={
        "mode": "margin", "entry": 0, "tp": 1, "sl": 1,
        "direction": "long", "leverage": 10, "margin": 500.0})
    assert r.status_code == 400
    assert "entry" in r.json()["detail"].lower()
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_calc_server.py -v`
Expected: FAIL — `/api/calc` 404.

- [ ] **Step 4: Implement** — in `server.py`, add the import and the endpoint.

Add near the top imports:

```python
from fastapi import FastAPI, HTTPException
from glory_hype.calc import compute_trade
```

(Replace the existing `from fastapi import FastAPI` line with the `HTTPException` version.)

Add inside `create_app`, before `return app`:

```python
    @app.post("/api/calc")
    async def calc(params: dict):
        try:
            return compute_trade(params)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_calc_server.py -v`
Expected: PASS (2 passed)

---

### Task 5: /api/chart/upload + /api/chart/pending endpoints

**Files:**
- Modify: `glory-hype/glory_hype/server.py`
- Test: `glory-hype/tests/test_chart_upload_server.py`

Context: multipart image upload → validate content-type → save via `record._write_image` into a charts dir → `insert_pending_chart_read`. The app needs to know where to save; add an optional `charts_dir` param to `create_app` (defaulting to record's default) so tests can point at tmp_path.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_chart_upload_server.py`:

```python
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_upload_creates_pending_and_lists(tmp_path):
    store = Store(str(tmp_path / "s.db"))
    app = create_app(store, charts_dir=str(tmp_path / "charts"))
    client = TestClient(app)
    r = client.post("/api/chart/upload",
                    files={"file": ("chart.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 200
    ts = r.json()["ts"]
    pend = client.get("/api/chart/pending").json()["pending"]
    assert len(pend) == 1
    assert pend[0]["ts"] == ts
    # image saved to disk
    from pathlib import Path
    assert Path(pend[0]["image_path"]).exists()


def test_upload_rejects_non_image(tmp_path):
    app = create_app(Store(str(tmp_path / "s2.db")), charts_dir=str(tmp_path / "c"))
    client = TestClient(app)
    r = client.post("/api/chart/upload",
                    files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with python-multipart pytest tests/test_chart_upload_server.py -v`
Expected: FAIL — `/api/chart/upload` 404.

- [ ] **Step 3: Implement** — update `server.py`.

Change imports (add `File`, `UploadFile`):

```python
from fastapi import FastAPI, HTTPException, File, UploadFile
```

Add the record helpers import near the top:

```python
from glory_hype.chart.record import _write_image, _DEFAULT_CHARTS_DIR
```

Change the `create_app` signature and capture `charts_dir`:

```python
def create_app(store: Store, charts_dir: str = _DEFAULT_CHARTS_DIR) -> FastAPI:
```

Add inside `create_app`, before `return app`:

```python
    @app.post("/api/chart/upload")
    async def chart_upload(file: UploadFile = File(...)):
        if not (file.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail="file must be an image")
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="image exceeds 10 MB")
        import time
        from pathlib import Path
        ts = int(time.time() * 1000)
        path = Path(charts_dir) / f"hype-{ts}.png"
        try:
            _write_image(path, data)
        except Exception:
            raise HTTPException(status_code=500, detail="failed to save image")
        store.insert_pending_chart_read(ts=ts, image_path=str(path))
        return {"ts": ts, "image_path": str(path), "status": "pending"}

    @app.get("/api/chart/pending")
    def chart_pending():
        return {"pending": store.pending_chart_reads()}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with python-multipart pytest tests/test_chart_upload_server.py -v`
Expected: PASS (2 passed)

---

### Task 6: CLI — chart --pending / --finalize

**Files:**
- Modify: `glory-hype/glory_hype/__main__.py`

No new test (thin CLI wiring over tested functions); verified by the manual workflow in Task 7 and the full suite staying green.

- [ ] **Step 1: Add args + branches**

In `glory-hype/glory_hype/__main__.py`: add `from glory_hype.chart.record import record_chart_read, finalize_chart_read` (extend the existing record import), and add a `--finalize` argument. Add `--ts` for the finalize target. Near the existing `--file`/`--image` args add:

```python
    p.add_argument("--pending", action="store_true",
                   help="list pending chart reads (for `chart`)")
    p.add_argument("--finalize", type=int, metavar="TS",
                   help="finalize the pending chart read at this ts (for `chart`)")
```

Replace the existing `elif args.cmd == "chart":` branch with:

```python
    elif args.cmd == "chart":
        if args.pending:
            print(_json.dumps(store.pending_chart_reads(), indent=2))
        elif args.finalize is not None:
            with open(args.file, encoding="utf-8") as f:
                data = _json.load(f)
            read = finalize_chart_read(store, args.finalize, data)
            print(_json.dumps(read.to_dict(), indent=2))
        else:
            with open(args.file, encoding="utf-8") as f:
                data = _json.load(f)
            image_bytes = None
            if args.image:
                with open(args.image, "rb") as f:
                    image_bytes = f.read()
            read = record_chart_read(store, data, image_bytes=image_bytes)
            print(_json.dumps(read.to_dict(), indent=2))
```

- [ ] **Step 2: Verify the CLI parses**

Run: `cd glory-hype && uv run python -m glory_hype chart --pending --db (some temp).db`
Use a temp db path; Expected: prints `[]` (no pending) without error. (On Windows use a path like `%TEMP%\t.db`.)

---

### Task 7: Dashboard — drop zone, pending queue, calculator

**Files:**
- Modify: `glory-hype/glory_hype/static/index.html`

No unit test (static markup); verified manually + by the endpoints' tests.

- [ ] **Step 1: Add the drop zone + pending queue + calculator** before `</body>` (after the Chart Read panel from v3):

```html
  <h2 style="font-size:14px;margin-top:24px;">Drop a chart to read</h2>
  <div id="drop" style="border:2px dashed #2b6cff;border-radius:10px;padding:24px;
       text-align:center;color:#8b97a7;cursor:pointer;">
    Drag a HYPE chart here, or click to pick a file
    <input id="file" type="file" accept="image/*" style="display:none;">
  </div>
  <div id="pending" style="font-size:12px;margin-top:8px;color:#8b97a7;"></div>

  <h2 style="font-size:14px;margin-top:24px;">Trade Calculator</h2>
  <div class="card">
    <div style="display:flex;flex-wrap:wrap;gap:8px;font-size:12px;">
      <label>Mode <select id="c_mode">
        <option value="margin">margin</option>
        <option value="position">position</option>
        <option value="risk_pct">risk %</option></select></label>
      <label>Dir <select id="c_dir"><option>long</option><option>short</option></select></label>
      <label>Entry <input id="c_entry" size="6"></label>
      <label>TP <input id="c_tp" size="6"></label>
      <label>SL <input id="c_sl" size="6"></label>
      <label>Lev <input id="c_lev" size="3" value="10"></label>
      <label>Margin <input id="c_margin" size="6"></label>
      <label>Notional <input id="c_notional" size="7"></label>
      <label>Account <input id="c_account" size="7"></label>
      <label>Risk% <input id="c_risk" size="4" placeholder="0.02"></label>
      <button id="c_go">Calculate</button>
    </div>
    <div id="c_out" style="margin-top:10px;font-size:13px;"></div>
  </div>

<script>
// --- drop-to-read ---
const drop = document.getElementById("drop"), fileInput = document.getElementById("file");
drop.onclick = () => fileInput.click();
drop.ondragover = e => { e.preventDefault(); drop.style.background = "#11161d"; };
drop.ondragleave = () => drop.style.background = "";
drop.ondrop = e => { e.preventDefault(); drop.style.background = ""; if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); };
fileInput.onchange = () => { if (fileInput.files[0]) upload(fileInput.files[0]); };
function upload(file){
  const fd = new FormData(); fd.append("file", file);
  drop.textContent = "Uploading…";
  fetch("/api/chart/upload", {method:"POST", body:fd}).then(r=>r.json()).then(()=>{
    drop.textContent = "Dropped — awaiting Glory's read. Drop another?"; loadPending();
  }).catch(()=>{ drop.textContent = "Upload failed. Try again."; });
}
function loadPending(){
  fetch("/api/chart/pending").then(r=>r.json()).then(d=>{
    const p = d.pending||[];
    document.getElementById("pending").innerHTML = p.length
      ? "⏳ "+p.length+" chart(s) awaiting Glory's read: "+p.map(x=>new Date(x.ts).toLocaleTimeString()).join(", ")
      : "";
  });
}
loadPending(); setInterval(loadPending, 10000);

// --- calculator ---
function num(id){ const v = parseFloat(document.getElementById(id).value); return isNaN(v)?undefined:v; }
document.getElementById("c_go").onclick = () => {
  const body = {mode:document.getElementById("c_mode").value,
    direction:document.getElementById("c_dir").value,
    entry:num("c_entry"), tp:num("c_tp"), sl:num("c_sl"), leverage:num("c_lev"),
    margin:num("c_margin"), position_notional:num("c_notional"),
    account:num("c_account"), risk_pct:num("c_risk")};
  fetch("/api/calc", {method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)}).then(async r=>{
      const out = document.getElementById("c_out");
      if (!r.ok){ out.innerHTML = '<span class="neg">'+(await r.json()).detail+'</span>'; return; }
      const d = await r.json();
      out.innerHTML = `Position: <b>$${d.position_notional}</b> (${d.position_coins} HYPE) ·
        Margin: $${d.margin}<br>
        TP PnL: <span class="pos">+$${d.pnl_at_tp}</span> (${(d.roi_tp*100).toFixed(1)}%) ·
        SL PnL: <span class="neg">$${d.pnl_at_sl}</span> (${(d.roi_sl*100).toFixed(1)}%)<br>
        R:R ${d.rr ?? '—'} · est. liq $${d.liq_price} <span style="color:#8b97a7">(gross, excl. fees)</span><br>
        ${(d.suggestions||[]).map(s=>'• '+s).join('<br>')}`;
    });
};
</script>
```

- [ ] **Step 2: Manual verification (after build)**

```
cd glory-hype
serve.bat   # http://localhost:5179
# Calculator: enter entry/tp/sl/lev/margin -> Calculate -> see position, PnL, R:R, liq, tips.
# Drop a chart image on the drop zone -> "awaiting Glory's read" + pending count appears.
```

- [ ] **Step 3: Run the full offline suite**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart pytest -q`
Expected: ALL green (v1 + v2 + v3 + v3.1).

---

### Task 8: Commit (GATED — only after user approval)

> Do NOT run until the user explicitly says to commit. This commits v3 + v3.1 together (v3 was never committed).

- [ ] **Step 1: Stage and commit**

```bash
cd E:/Glory
git add glory-hype docs/superpowers/specs/2026-05-30-hype-chart-reader-design.md \
  docs/superpowers/specs/2026-05-30-hype-dashboard-interactivity-design.md \
  docs/superpowers/plans/2026-05-30-hype-chart-reader.md \
  docs/superpowers/plans/2026-05-30-hype-dashboard-interactivity.md
git commit -m "feat(hype): v3 chart reader + v3.1 drop-to-read & trade calculator

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Trade calculator, 3 modes, full outputs + suggestions + validation → Task 1 ✓
- chart_reads status + pending/finalize + latest filters read → Task 2 ✓
- finalize_chart_read (preserves image_path) → Task 3 ✓
- /api/calc (400 on ValueError) → Task 4 ✓
- /api/chart/upload (image validation, 10MB cap, save, pending row) + /api/chart/pending → Task 5 ✓
- CLI --pending / --finalize → Task 6 ✓
- Dashboard drop zone + pending queue + calculator form → Task 7 ✓
- python-multipart dependency → Task 4 step 1 ✓
- Existing v3 CLI read path unchanged (status defaults 'read') → Task 2 ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code; commands have expected output.

**Type consistency:** `compute_trade(params: dict) -> dict` keys (`position_notional`, `position_coins`, `margin`, `pnl_at_tp`, `pnl_at_sl`, `roi_tp`, `roi_sl`, `rr`, `liq_price`, `suggestions`) consistent across calc impl, calc test, /api/calc, and dashboard JS. Store methods (`insert_pending_chart_read`, `pending_chart_reads`, `finalize_chart_read`, `insert_chart_read`, `latest_chart_read`) named identically across db, record, server, CLI, tests. `record.finalize_chart_read(store, ts, data)` vs `Store.finalize_chart_read(ts, read_dict)` are distinct (module helper wraps the Store method) — names match their call sites. `create_app(store, charts_dir=...)` signature matches the upload test and `_DEFAULT_CHARTS_DIR` import. `_write_image`/`_DEFAULT_CHARTS_DIR` reused from record.py (defined in v3).

**Note:** Task 5 reuses `record._write_image` and `_DEFAULT_CHARTS_DIR` (underscore-prefixed) across modules — acceptable here since record.py is our own module and these are stable internal helpers; flagged so a reviewer doesn't see it as a boundary violation.
