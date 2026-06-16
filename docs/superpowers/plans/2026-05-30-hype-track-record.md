# HYPE Track Record + Learning (v5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-resolve each v4 TradeCall's outcome from our stored 1m candles, compute the real win-rate/expectancy, surface it on the dashboard, and feed it back into the v4 decision context.

**Architecture:** Pure resolution (`resolve_outcome`) + pure stats (`compute_stats`); a resolver updates open calls using v1 candle data; Store gains a `status` column + outcome methods; the v4 engine surfaces the track summary in its inputs. No ML — the compounding record is the learning.

**Tech Stack:** Python 3.12, `uv`, stdlib `sqlite3`, `fastapi`, `pytest`. No new deps.

> **Git note:** prior work committed through 3d43994f; v4 is built but uncommitted. Do NOT commit per-task. Final commit (Task 8) is gated and bundles v4 + v5.

Run offline tests with:
`cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart pytest -q`

---

## File Structure

```
glory-hype/glory_hype/
  db.py                # MODIFY: trade_calls.status + migration; open_trade_calls,
                       #         update_call_outcome, candles_since; insert sets status
  track/
    __init__.py
    outcomes.py        # pure: resolve_outcome(call, candles)
    stats.py           # pure: compute_stats(resolved)
    resolver.py        # resolve_open_calls(store), track_summary(store)
  decision/engine.py   # MODIFY: add track_summary to inputs
  server.py            # MODIFY: /api/track
  static/index.html    # MODIFY: Track Record panel
  __main__.py          # MODIFY: `track` subcommand
  tests/
    test_outcomes.py
    test_track_stats.py
    test_resolver.py
    test_track_server.py
```

---

### Task 1: Outcome resolution (pure)

**Files:**
- Create: `glory-hype/glory_hype/track/__init__.py`, `glory-hype/glory_hype/track/outcomes.py`
- Test: `glory-hype/tests/test_outcomes.py`

- [ ] **Step 1: Create the package init**

`glory-hype/glory_hype/track/__init__.py`:

```python
"""HYPE track record (v5): resolve call outcomes from candles + compute stats."""
```

- [ ] **Step 2: Write the failing test**

`glory-hype/tests/test_outcomes.py`:

```python
from glory_hype.track.outcomes import resolve_outcome


def _candle(open_ts, h, l):
    return {"interval": "1m", "open_ts": open_ts, "close_ts": open_ts + 59999,
            "o": l, "h": h, "l": l, "c": h, "v": 1.0, "n": 1}


def _call(decision="long", entry=100.0, tp=110.0, sl=95.0, ts=0):
    return {"decision": decision, "entry": entry, "tp": tp, "sl": sl,
            "generated_at": ts}


def test_long_win():
    candles = [_candle(1, 102, 99), _candle(2, 111, 108)]  # 2nd hits tp 110
    o = resolve_outcome(_call(), candles)
    assert o["status"] == "win"
    assert o["exit_price"] == 110.0
    assert o["r_multiple"] == 2.0          # reward 10 / risk 5
    assert o["ambiguous"] is False


def test_long_loss():
    candles = [_candle(1, 103, 96), _candle(2, 104, 94)]   # 2nd hits sl 95
    o = resolve_outcome(_call(), candles)
    assert o["status"] == "loss"
    assert o["exit_price"] == 95.0
    assert o["r_multiple"] == -1.0


def test_long_open():
    candles = [_candle(1, 103, 97), _candle(2, 104, 98)]   # neither tp nor sl
    o = resolve_outcome(_call(), candles)
    assert o["status"] == "open"
    assert o["r_multiple"] is None


def test_long_straddle_is_loss():
    candles = [_candle(1, 111, 94)]   # one candle spans both tp and sl
    o = resolve_outcome(_call(), candles)
    assert o["status"] == "loss"
    assert o["ambiguous"] is True


def test_short_win():
    # short entry 100 tp 90 sl 104; candle low 89 hits tp
    candles = [_candle(1, 101, 89)]
    o = resolve_outcome(_call(decision="short", tp=90.0, sl=104.0), candles)
    assert o["status"] == "win"
    assert o["r_multiple"] == 2.5         # reward 10 / risk 4


def test_short_loss():
    candles = [_candle(1, 105, 99)]       # high 105 hits sl 104
    o = resolve_outcome(_call(decision="short", tp=90.0, sl=104.0), candles)
    assert o["status"] == "loss"


def test_no_trade_is_na():
    o = resolve_outcome({"decision": "no_trade", "generated_at": 0}, [])
    assert o["status"] == "n/a"


def test_missing_levels_is_na():
    o = resolve_outcome({"decision": "long", "entry": 100, "tp": None,
                         "sl": 95, "generated_at": 0}, [_candle(1, 200, 50)])
    assert o["status"] == "n/a"
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_outcomes.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement**

`glory-hype/glory_hype/track/outcomes.py`:

```python
"""Pure outcome resolution: did a call hit TP or SL first, per our candles?"""

_NA = {"status": "n/a", "exit_price": None, "exit_ts": None,
       "r_multiple": None, "ambiguous": False}


def resolve_outcome(call: dict, candles: list) -> dict:
    decision = call.get("decision")
    entry, tp, sl = call.get("entry"), call.get("tp"), call.get("sl")
    if decision not in ("long", "short") or entry is None or tp is None or sl is None:
        return dict(_NA)

    risk = abs(entry - sl)
    reward = abs(tp - entry)
    win_r = round(reward / risk, 4) if risk else None

    def win(c):
        return {"status": "win", "exit_price": float(tp), "exit_ts": c["open_ts"],
                "r_multiple": win_r, "ambiguous": False}

    def loss(c, ambiguous=False):
        return {"status": "loss", "exit_price": float(sl), "exit_ts": c["open_ts"],
                "r_multiple": -1.0, "ambiguous": ambiguous}

    for c in candles:
        hi, lo = c["h"], c["l"]
        if decision == "long":
            hit_sl, hit_tp = lo <= sl, hi >= tp
        else:  # short
            hit_sl, hit_tp = hi >= sl, lo <= tp
        if hit_sl and hit_tp:
            return loss(c, ambiguous=True)   # conservative: assume stop first
        if hit_sl:
            return loss(c)
        if hit_tp:
            return win(c)
    return {"status": "open", "exit_price": None, "exit_ts": None,
            "r_multiple": None, "ambiguous": False}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_outcomes.py -v`
Expected: PASS (8 passed)

---

### Task 2: Stats (pure)

**Files:**
- Create: `glory-hype/glory_hype/track/stats.py`
- Test: `glory-hype/tests/test_track_stats.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_track_stats.py`:

```python
from glory_hype.track.stats import compute_stats


def test_known_set():
    resolved = [
        {"status": "win", "r_multiple": 2.0},
        {"status": "win", "r_multiple": 2.0},
        {"status": "loss", "r_multiple": -1.0},
        {"status": "open", "r_multiple": None},
        {"status": "n/a", "r_multiple": None},
    ]
    s = compute_stats(resolved)
    assert s["n_closed"] == 3
    assert s["wins"] == 2 and s["losses"] == 1
    assert s["open_count"] == 1
    assert round(s["win_rate"], 4) == round(2 / 3, 4)
    assert s["avg_win_r"] == 2.0
    assert s["avg_loss_r"] == -1.0
    # expectancy = 2/3*2 + 1/3*(-1) = 1.0
    assert round(s["expectancy_r"], 4) == 1.0
    # profit factor = (2+2) / abs(-1) = 4.0
    assert s["profit_factor"] == 4.0


def test_empty_safe():
    s = compute_stats([])
    assert s["n_closed"] == 0
    assert s["win_rate"] is None
    assert s["expectancy_r"] is None
    assert s["profit_factor"] is None


def test_no_losses_profit_factor_none():
    s = compute_stats([{"status": "win", "r_multiple": 2.0}])
    assert s["profit_factor"] is None      # no losses -> undefined
    assert s["win_rate"] == 1.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_track_stats.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/track/stats.py`:

```python
"""Pure track-record statistics over resolved outcomes."""


def compute_stats(resolved: list) -> dict:
    wins = [r for r in resolved if r.get("status") == "win"]
    losses = [r for r in resolved if r.get("status") == "loss"]
    opens = [r for r in resolved if r.get("status") == "open"]
    n_closed = len(wins) + len(losses)

    win_rate = (len(wins) / n_closed) if n_closed else None
    avg_win_r = (sum(w["r_multiple"] for w in wins) / len(wins)) if wins else None
    avg_loss_r = (sum(l["r_multiple"] for l in losses) / len(losses)) if losses else None

    if n_closed and win_rate is not None:
        aw = avg_win_r or 0.0
        al = avg_loss_r or 0.0
        expectancy_r = win_rate * aw + (1 - win_rate) * al
    else:
        expectancy_r = None

    loss_sum = abs(sum(l["r_multiple"] for l in losses))
    win_sum = sum(w["r_multiple"] for w in wins)
    profit_factor = (win_sum / loss_sum) if loss_sum else None

    return {
        "n_closed": n_closed, "wins": len(wins), "losses": len(losses),
        "open_count": len(opens),
        "win_rate": win_rate, "avg_win_r": avg_win_r, "avg_loss_r": avg_loss_r,
        "expectancy_r": expectancy_r, "profit_factor": profit_factor,
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_track_stats.py -v`
Expected: PASS (3 passed)

---

### Task 3: Store — status column + outcome/candle methods

**Files:**
- Modify: `glory-hype/glory_hype/db.py`
- Test: `glory-hype/tests/test_resolver.py` (store portion)

Context: `trade_calls` needs a `status` column (default `'open'`), set on insert based on
decision; methods to list open calls, update an outcome, and fetch candles after a ts.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_resolver.py`:

```python
from glory_hype.db import Store


def _candle(ts, h, l):
    return {"interval": "1m", "open_ts": ts, "close_ts": ts + 59999,
            "o": l, "h": h, "l": l, "c": h, "v": 1.0, "n": 1}


def test_store_status_open_and_candles_since(tmp_path):
    s = Store(str(tmp_path / "r.db"))
    s.insert_trade_call({"generated_at": 1000, "decision": "long", "entry": 100,
                         "tp": 110, "sl": 95})
    s.insert_trade_call({"generated_at": 1100, "decision": "no_trade",
                         "gates_failed": ["x"]})
    opens = s.open_trade_calls()
    assert len(opens) == 1 and opens[0]["decision"] == "long"   # no_trade excluded
    for c in [_candle(900, 1, 1), _candle(1500, 111, 108), _candle(2000, 112, 109)]:
        s.insert_candle(c)
    later = s.candles_since("1m", 1000)
    assert [c["open_ts"] for c in later] == [1500, 2000]         # strictly after ts


def test_store_update_outcome(tmp_path):
    s = Store(str(tmp_path / "r2.db"))
    s.insert_trade_call({"generated_at": 1000, "decision": "long", "entry": 100,
                         "tp": 110, "sl": 95})
    s.update_call_outcome(1000, {"status": "win", "exit_price": 110.0,
                                 "r_multiple": 2.0, "ambiguous": False})
    s.set_setting  # ensure store import path ok
    latest = s.latest_trade_call()
    assert latest["status"] == "win"
    assert latest["r_multiple"] == 2.0
    assert latest["exit_price"] == 110.0
    assert s.open_trade_calls() == []        # no longer open
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_resolver.py -v`
Expected: FAIL — `open_trade_calls` missing.

- [ ] **Step 3: Add status to trade_calls SCHEMA** — change the `trade_calls` CREATE in `db.py` SCHEMA to:

```sql
CREATE TABLE IF NOT EXISTS trade_calls (
    generated_at INTEGER PRIMARY KEY,
    decision TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calls_ts ON trade_calls(generated_at);
CREATE INDEX IF NOT EXISTS idx_calls_status ON trade_calls(status);
```

Extend `_migrate` (added in v3.1) to also add the column to existing DBs — append inside `_migrate`:

```python
        cols2 = [r["name"] for r in self.conn.execute(
            "PRAGMA table_info(trade_calls)").fetchall()]
        if cols2 and "status" not in cols2:
            self.conn.execute(
                "ALTER TABLE trade_calls ADD COLUMN status TEXT NOT NULL DEFAULT 'open'")
```

(Note `cols2` is empty if the table doesn't exist yet on a brand-new DB — guard with `if cols2 and ...`; the CREATE TABLE already includes the column for new DBs.)

- [ ] **Step 4: Update `insert_trade_call` + add methods** — replace the existing `insert_trade_call` and add the three methods in `db.py`:

```python
    def insert_trade_call(self, call: dict) -> None:
        status = "no_trade" if call.get("decision") == "no_trade" else \
            call.get("status", "open")
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO trade_calls (generated_at, decision, status, json) "
                "VALUES (?,?,?,?)",
                (call["generated_at"], call.get("decision"), status, json.dumps(call)))
            self.conn.commit()

    def open_trade_calls(self) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT json FROM trade_calls WHERE status='open' "
                "ORDER BY generated_at").fetchall()
        return [json.loads(r["json"]) for r in rows]

    def update_call_outcome(self, generated_at: int, outcome: dict) -> None:
        with self._lock:
            r = self.conn.execute(
                "SELECT json FROM trade_calls WHERE generated_at=?",
                (generated_at,)).fetchone()
            if not r:
                return
            call = json.loads(r["json"])
            call.update({"status": outcome["status"],
                         "exit_price": outcome.get("exit_price"),
                         "r_multiple": outcome.get("r_multiple"),
                         "ambiguous": outcome.get("ambiguous", False),
                         "resolved_at": int(__import__("time").time() * 1000)})
            self.conn.execute(
                "UPDATE trade_calls SET status=?, json=? WHERE generated_at=?",
                (outcome["status"], json.dumps(call), generated_at))
            self.conn.commit()

    def candles_since(self, interval: str, since_ts: int) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM candles WHERE interval=? AND open_ts > ? ORDER BY open_ts",
                (interval, since_ts)).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_resolver.py -v`
Expected: PASS (the 2 store tests; resolver test added next)

- [ ] **Step 6: Full suite (no regression — v4 trade_calls tests still pass)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart pytest -q`
Expected: all prior pass (status defaults 'open'; v4 `test_settings_store` trade_calls round-trip still works — it stores no_trade with status 'no_trade' and a long with 'open', and latest_trade_call still returns the json).

---

### Task 4: Resolver + track summary

**Files:**
- Create: `glory-hype/glory_hype/track/resolver.py`
- Test: `glory-hype/tests/test_resolver.py` (append resolver test)

- [ ] **Step 1: Append the failing test** to `tests/test_resolver.py`:

```python
def test_resolve_open_calls_marks_win_and_idempotent(tmp_path):
    from glory_hype.track.resolver import resolve_open_calls, track_summary
    s = Store(str(tmp_path / "r3.db"))
    s.insert_trade_call({"generated_at": 1000, "decision": "long", "entry": 100,
                         "tp": 110, "sl": 95})
    for c in [_candle(1500, 105, 99), _candle(2000, 111, 108)]:  # 2nd hits tp
        s.insert_candle(c)
    stats = resolve_open_calls(s)
    assert stats["wins"] == 1 and stats["n_closed"] == 1
    assert s.latest_trade_call()["status"] == "win"
    assert s.open_trade_calls() == []          # resolved
    # idempotent: re-run changes nothing
    stats2 = resolve_open_calls(s)
    assert stats2["wins"] == 1 and stats2["n_closed"] == 1
    summ = track_summary(s)
    assert summ["win_rate"] == 1.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_resolver.py::test_resolve_open_calls_marks_win_and_idempotent -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/track/resolver.py`:

```python
"""Resolve open trade calls against stored candles; summarize the track record."""

from glory_hype.track.outcomes import resolve_outcome
from glory_hype.track.stats import compute_stats


def resolve_open_calls(store) -> dict:
    for call in store.open_trade_calls():
        candles = store.candles_since("1m", call["generated_at"])
        outcome = resolve_outcome(call, candles)
        if outcome["status"] in ("win", "loss"):
            store.update_call_outcome(call["generated_at"], outcome)
    return track_summary(store)


def track_summary(store) -> dict:
    return compute_stats(store.recent_trade_calls(since_ts=0))
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_resolver.py -v`
Expected: PASS (3 passed)

---

### Task 5: Feed track record into the v4 decision context

**Files:**
- Modify: `glory-hype/glory_hype/decision/engine.py`
- Test: extend `glory-hype/tests/test_decision_engine.py`

- [ ] **Step 1: Append the failing test** to `tests/test_decision_engine.py`:

```python
def test_call_inputs_include_track_record(tmp_path):
    from glory_hype.db import Store
    from glory_hype.decision.engine import record_call
    s = Store(str(tmp_path / "tr.db"))
    _fresh(s)
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.7, "rationale": "aligned"})
    assert "track_record" in call.inputs
    assert "win_rate" in call.inputs["track_record"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_decision_engine.py::test_call_inputs_include_track_record -v`
Expected: FAIL — `track_record` not in inputs.

- [ ] **Step 3: Implement** — in `engine.py`, add the import and include the summary in `inputs`. Add near the top imports:

```python
from glory_hype.track.resolver import track_summary
```

Change the `inputs` dict construction (right after gathering ctx/conclusion/chart_read) to:

```python
    inputs = {"ctx_ts": (ctx or {}).get("ts"),
              "conclusion_at": (conclusion or {}).get("generated_at"),
              "chart_read_ts": (chart_read or {}).get("ts"),
              "track_record": track_summary(store)}
```

(`inputs` is then used in every return path, so no other change needed.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_decision_engine.py -v`
Expected: PASS (all decision-engine tests, including the new one)

---

### Task 6: Server — /api/track

**Files:**
- Modify: `glory-hype/glory_hype/server.py`
- Test: `glory-hype/tests/test_track_server.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_track_server.py`:

```python
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_track_endpoint(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.insert_trade_call({"generated_at": 1000, "decision": "long", "entry": 100,
                         "tp": 110, "sl": 95})
    s.update_call_outcome(1000, {"status": "win", "exit_price": 110.0,
                                 "r_multiple": 2.0, "ambiguous": False})
    app = create_app(s)
    client = TestClient(app)
    r = client.get("/api/track")
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["wins"] == 1
    assert body["stats"]["win_rate"] == 1.0
    assert len(body["recent"]) == 1
    assert body["recent"][0]["status"] == "win"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_track_server.py -v`
Expected: FAIL — `/api/track` 404.

- [ ] **Step 3: Implement** — add inside `create_app` in `server.py`, before `return app`. Add import at top: `from glory_hype.track.resolver import track_summary`.

```python
    @app.get("/api/track")
    def track():
        calls = store.recent_trade_calls(since_ts=0)
        closed = [c for c in calls if c.get("status") in ("win", "loss")]
        return {"stats": track_summary(store), "recent": closed[:20]}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_track_server.py -v`
Expected: PASS (1 passed)

---

### Task 7: CLI `track` + dashboard Track Record panel

**Files:**
- Modify: `glory-hype/glory_hype/__main__.py`
- Modify: `glory-hype/glory_hype/static/index.html`

No new test (thin CLI + static markup); verified by endpoint test + manual.

- [ ] **Step 1: Add the `track` CLI** — in `__main__.py`: add `"track"` to `choices`, add `from glory_hype.track.resolver import resolve_open_calls`, and add the branch:

```python
    elif args.cmd == "track":
        stats = resolve_open_calls(store)
        print(_json.dumps(stats, indent=2))
```

- [ ] **Step 2: Add the Track Record panel** — in `static/index.html`, before `</body>`:

```html
  <h2 style="font-size:14px;margin-top:24px;">Track Record</h2>
  <div id="track" class="card">No closed trades yet.</div>

<script>
function renderTrack(d){
  const s=d.stats||{}, el=document.getElementById("track");
  if(!s.n_closed){ el.textContent="No closed trades yet ("+(s.open_count||0)+" open)."; return; }
  const wr = s.win_rate!=null ? (s.win_rate*100).toFixed(1)+"%" : "—";
  const exp = s.expectancy_r!=null ? s.expectancy_r.toFixed(2)+"R" : "—";
  const pf = s.profit_factor!=null ? s.profit_factor.toFixed(2) : "—";
  el.innerHTML = `<div class="val">Win rate ${wr} · ${exp} expectancy</div>
    <div style="font-size:12px;margin-top:4px;">${s.wins}W / ${s.losses}L · ${s.open_count} open · profit factor ${pf}</div>
    <table style="margin-top:8px;"><thead><tr><th>Decision</th><th>R</th><th>Status</th></tr></thead><tbody>`
    + (d.recent||[]).map(c=>`<tr><td>${c.decision} @ ${c.entry}</td>
        <td class="${c.r_multiple>0?'pos':'neg'}">${c.r_multiple}</td><td>${c.status}</td></tr>`).join('')
    + `</tbody></table>`;
}
function loadTrack(){ fetch("/api/track").then(r=>r.json()).then(renderTrack); }
loadTrack(); setInterval(loadTrack, 20000);
</script>
```

- [ ] **Step 3: Run the full offline suite**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart pytest -q`
Expected: ALL green (v1–v5).

- [ ] **Step 4: Manual check**

```
cd glory-hype
python -m glory_hype track     # resolves open calls against candles, prints stats
serve.bat                      # http://localhost:5179 -> Track Record panel
```

---

### Task 8: Commit v4 + v5 (GATED — only after user approval)

> Do NOT run until the user explicitly says to commit. Bundles v4 + v5 (v4 is uncommitted).

- [ ] **Step 1: Stage and commit**

```bash
cd E:/Glory
git add glory-hype \
  docs/superpowers/specs/2026-05-30-hype-decision-engine-design.md \
  docs/superpowers/plans/2026-05-30-hype-decision-engine.md \
  docs/superpowers/specs/2026-05-30-hype-track-record-design.md \
  docs/superpowers/plans/2026-05-30-hype-track-record.md
git commit -m "feat(hype): v4 decision engine + v5 track record & learning

v4: gated, sized long/short TradeCall fusing live data + narrative + chart read;
hard gates (stale/flagged/low-R:R/liq-inside-stop) override to no_trade; sizing via
the risk-% calculator using dashboard-set account/risk/leverage.

v5: auto-resolve each call's outcome from our 1m candles (TP-before-SL = win,
SL-first = loss, straddle = conservative loss), compute real win-rate / expectancy /
profit factor, surface a Track Record panel, and feed the record back into the v4
decision context. Completes the v1-v5 arc.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- `resolve_outcome` (long/short win/loss/open, straddle→loss, n/a) → Task 1 ✓
- `compute_stats` (win-rate/expectancy/profit-factor, None-safe) → Task 2 ✓
- Store status column + migration + open_trade_calls/update_call_outcome/candles_since;
  insert sets status → Task 3 ✓
- `resolve_open_calls` + `track_summary`, idempotent → Task 4 ✓
- Track record fed into v4 decision inputs → Task 5 ✓
- `/api/track` → Task 6 ✓
- `track` CLI + dashboard panel → Task 7 ✓

**Placeholder scan:** No TBD/TODO; complete code in every step; commands have expected output.

**Type consistency:** `resolve_outcome(call, candles)` output keys (`status/exit_price/exit_ts/r_multiple/ambiguous`) match `update_call_outcome` and `compute_stats` consumers. `compute_stats` output keys (`n_closed/wins/losses/open_count/win_rate/avg_win_r/avg_loss_r/expectancy_r/profit_factor`) match the dashboard renderer and `/api/track`. Store methods (`open_trade_calls/update_call_outcome/candles_since/insert_trade_call/recent_trade_calls/latest_trade_call`) consistent across db/resolver/server/tests. `track_summary(store)` reused in engine + server. Candle dict keys (`open_ts/h/l`) match v1's `insert_candle`/`candles_since` shape. `_migrate` extension guards the empty-table case so brand-new DBs (table created with the column) don't double-add.
