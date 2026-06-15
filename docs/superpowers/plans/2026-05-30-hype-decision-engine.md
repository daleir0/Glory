# HYPE Decision Engine (v4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fuse v1 live data + v2 narrative conclusion + v3 chart read into a decisive, sized long/short TradeCall — or an explicit no_trade when hard gates fail.

**Architecture:** Deterministic code gathers the three inputs, runs hard gates, sizes via the v3.1 calculator, and persists; the Claude Code agent supplies the directional judgment (direction/entry/TP/SL/confidence/rationale). A failed gate overrides the agent to no_trade. Account/risk/leverage are settings stored in hype.db and set on the dashboard.

**Tech Stack:** Python 3.12, `uv`, stdlib `sqlite3`, `fastapi`, `pytest`. Reuses `calc.compute_trade`. No new deps.

> **Git note:** prior work committed through 3d43994f. Do NOT commit per-task. Final commit (Task 8) is gated on explicit user approval.

Run offline tests with:
`cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart pytest -q`

---

## File Structure

```
glory-hype/glory_hype/
  config.py            # MODIFY: MIN_RR, default risk/leverage, staleness thresholds
  db.py                # MODIFY: settings table + trade_calls table + methods
  decision/
    __init__.py
    gates.py           # pure: evaluate_gates(ctx, conclusion, chart_read, now_ms, cfg) -> list[str]
    tradecall.py       # TradeCall dataclass + parse_judgment (defensive)
    engine.py          # record_call(store, judgment): gather + gate + size + persist
  server.py            # MODIFY: /api/decision (GET), /api/settings (GET/POST)
  static/index.html    # MODIFY: Decision panel + account/risk/leverage settings inputs
  __main__.py          # MODIFY: `decide` subcommand
  tests/
    test_gates.py
    test_tradecall.py
    test_decision_engine.py
    test_settings_store.py
    test_decision_server.py
```

---

### Task 1: Config thresholds

**Files:**
- Modify: `glory-hype/glory_hype/config.py`
- Test: `glory-hype/tests/test_decision_config.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_decision_config.py`:

```python
from glory_hype import config


def test_decision_thresholds_present():
    assert config.MIN_RR == 1.0
    assert config.NARRATIVE_STALE_MS == 6 * 60 * 60 * 1000
    assert config.CTX_STALE_MS == 5 * 60 * 1000
    assert config.DEFAULT_RISK_PCT == 0.01
    assert config.DEFAULT_LEVERAGE == 10
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_decision_config.py -v`
Expected: FAIL — attributes missing.

- [ ] **Step 3: Implement** — append to `glory-hype/glory_hype/config.py`:

```python
# --- v4 decision engine ---
MIN_RR = 1.0                              # reject calls below this reward:risk
NARRATIVE_STALE_MS = 6 * 60 * 60 * 1000   # 6h
CTX_STALE_MS = 5 * 60 * 1000              # 5 min
DEFAULT_RISK_PCT = 0.01                   # 1% of account risked per trade
DEFAULT_LEVERAGE = 10
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_decision_config.py -v`
Expected: PASS (1 passed)

---

### Task 2: Hard gates (pure)

**Files:**
- Create: `glory-hype/glory_hype/decision/__init__.py`, `glory-hype/glory_hype/decision/gates.py`
- Test: `glory-hype/tests/test_gates.py`

- [ ] **Step 1: Create the package init**

`glory-hype/glory_hype/decision/__init__.py`:

```python
"""HYPE decision engine (v4): fuse data+narrative+chart into a sized call."""
```

- [ ] **Step 2: Write the failing test**

`glory-hype/tests/test_gates.py`:

```python
from glory_hype.decision.gates import evaluate_gates
from glory_hype import config

NOW = 1_000_000_000_000


def _ctx(ts=NOW):
    return {"ts": ts, "mark_px": 67.5}


def _conc(at=NOW, bias="bullish", conf=0.7, cautions=None):
    return {"generated_at": at, "bias": bias, "confidence": conf,
            "caution_flags": cautions or []}


def _chart(flags=None, position=None):
    return {"flags": flags or [], "trend": "range", "current_price": 67.5,
            "position": position or {"entry": 67.4, "sl": 66.7, "tp": 68.2}}


def test_all_pass_returns_empty():
    assert evaluate_gates(_ctx(), _conc(), _chart(), NOW, config) == []


def test_missing_chart_read():
    g = evaluate_gates(_ctx(), _conc(), None, NOW, config)
    assert any("chart" in x.lower() for x in g)


def test_flagged_chart():
    g = evaluate_gates(_ctx(), _conc(), _chart(flags=["diverges 33%"]), NOW, config)
    assert any("flag" in x.lower() for x in g)


def test_stale_ctx():
    old = NOW - config.CTX_STALE_MS - 1
    g = evaluate_gates(_ctx(ts=old), _conc(), _chart(), NOW, config)
    assert any("market data" in x.lower() or "ctx" in x.lower() for x in g)


def test_stale_narrative():
    old = NOW - config.NARRATIVE_STALE_MS - 1
    g = evaluate_gates(_ctx(), _conc(at=old), _chart(), NOW, config)
    assert any("narrative" in x.lower() and "stale" in x.lower() for x in g)


def test_unavailable_narrative():
    g = evaluate_gates(_ctx(), _conc(cautions=["synthesis unavailable"]), _chart(), NOW, config)
    assert any("unavailable" in x.lower() for x in g)


def test_missing_narrative():
    g = evaluate_gates(_ctx(), None, _chart(), NOW, config)
    assert any("narrative" in x.lower() for x in g)


def test_missing_ctx():
    g = evaluate_gates(None, _conc(), _chart(), NOW, config)
    assert any("market data" in x.lower() for x in g)
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_gates.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement**

`glory-hype/glory_hype/decision/gates.py`:

```python
"""Pure hard gates for the decision engine. Any returned reason => no_trade.

R:R and liquidation gates are applied later in the engine (they need sizing);
these gates cover input freshness/validity/availability."""


def evaluate_gates(ctx, conclusion, chart_read, now_ms, cfg) -> list:
    reasons = []

    if not ctx:
        reasons.append("No live market data (ctx) available.")
    elif now_ms - ctx.get("ts", 0) > cfg.CTX_STALE_MS:
        reasons.append("Live market data is stale (collector may be down).")

    if not conclusion:
        reasons.append("No narrative conclusion available.")
    else:
        cautions = " ".join(conclusion.get("caution_flags", [])).lower()
        if "synthesis unavailable" in cautions:
            reasons.append("Narrative synthesis unavailable.")
        elif now_ms - conclusion.get("generated_at", 0) > cfg.NARRATIVE_STALE_MS:
            reasons.append("Narrative conclusion is stale (>6h old).")

    if not chart_read:
        reasons.append("No chart read on record to anchor entry/TP/SL.")
    elif chart_read.get("flags"):
        reasons.append("Chart read is flagged (data integrity): "
                       + "; ".join(chart_read["flags"]))

    return reasons
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_gates.py -v`
Expected: PASS (8 passed)

---

### Task 3: TradeCall + judgment parsing

**Files:**
- Create: `glory-hype/glory_hype/decision/tradecall.py`
- Test: `glory-hype/tests/test_tradecall.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_tradecall.py`:

```python
from glory_hype.decision.tradecall import TradeCall, parse_judgment, no_trade


def test_parse_valid_judgment():
    j = parse_judgment({"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                        "confidence": 0.7, "rationale": "aligned"})
    assert j["decision"] == "long"
    assert j["entry"] == 67.4 and j["tp"] == 68.2 and j["sl"] == 66.7
    assert j["confidence"] == 0.7


def test_parse_clamps_confidence_and_validates_decision():
    j = parse_judgment({"decision": "sideways", "entry": 1, "tp": 2, "sl": 0.5,
                        "confidence": 5})
    assert j["decision"] == "no_trade"      # invalid direction -> no_trade
    assert j["confidence"] == 1.0           # clamped


def test_parse_missing_levels_forces_no_trade():
    j = parse_judgment({"decision": "long", "entry": None, "tp": 68.2, "sl": 66.7})
    assert j["decision"] == "no_trade"
    assert "incomplete" in j["rationale"].lower()


def test_no_trade_factory():
    c = no_trade(["bad"], generated_at=5)
    assert c.decision == "no_trade"
    assert c.gates_failed == ["bad"]
    assert c.confidence == 0.0
    assert c.to_dict()["generated_at"] == 5


def test_tradecall_to_dict_roundtrips():
    c = TradeCall(decision="long", entry=67.4, tp=68.2, sl=66.7,
                  position_notional=100.0, position_coins=1.48, margin=10.0,
                  leverage=10, rr=1.19, liq_price=60.6, confidence=0.7,
                  rationale="x", gates_failed=[], inputs={"ctx_ts": 1}, generated_at=9)
    d = c.to_dict()
    assert d["decision"] == "long" and d["rr"] == 1.19 and d["inputs"]["ctx_ts"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_tradecall.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/decision/tradecall.py`:

```python
"""TradeCall dataclass + defensive parsing of the agent's directional judgment."""

from dataclasses import asdict, dataclass, field

_DIRECTIONS = {"long", "short"}


@dataclass
class TradeCall:
    decision: str                         # long | short | no_trade
    entry: float | None = None
    tp: float | None = None
    sl: float | None = None
    position_notional: float | None = None
    position_coins: float | None = None
    margin: float | None = None
    leverage: float | None = None
    rr: float | None = None
    liq_price: float | None = None
    confidence: float = 0.0
    rationale: str = ""
    gates_failed: list = field(default_factory=list)
    inputs: dict = field(default_factory=dict)
    generated_at: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def no_trade(gates_failed, generated_at, rationale="") -> TradeCall:
    return TradeCall(decision="no_trade", confidence=0.0,
                     gates_failed=list(gates_failed), generated_at=generated_at,
                     rationale=rationale or "No trade: " + "; ".join(gates_failed))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_judgment(j: dict) -> dict:
    """Normalize the agent's judgment. Returns a dict with at least `decision`,
    `entry`, `tp`, `sl`, `confidence`, `rationale`. Invalid direction or missing
    entry/sl downgrade to no_trade."""
    d = j if isinstance(j, dict) else {}
    decision = str(d.get("decision", "")).lower()
    entry, tp, sl = _num(d.get("entry")), _num(d.get("tp")), _num(d.get("sl"))
    conf = _num(d.get("confidence")) or 0.0
    conf = max(0.0, min(1.0, conf))
    rationale = str(d.get("rationale", ""))
    if decision not in _DIRECTIONS:
        return {"decision": "no_trade", "entry": entry, "tp": tp, "sl": sl,
                "confidence": conf,
                "rationale": rationale or "Invalid/!directional judgment."}
    if entry is None or sl is None:
        return {"decision": "no_trade", "entry": entry, "tp": tp, "sl": sl,
                "confidence": conf,
                "rationale": "Incomplete judgment: entry/sl missing."}
    return {"decision": decision, "entry": entry, "tp": tp, "sl": sl,
            "confidence": conf, "rationale": rationale}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_tradecall.py -v`
Expected: PASS (5 passed)

---

### Task 4: Settings + trade_calls store

**Files:**
- Modify: `glory-hype/glory_hype/db.py` (SCHEMA + methods)
- Test: `glory-hype/tests/test_settings_store.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_settings_store.py`:

```python
from glory_hype.db import Store


def test_settings_get_set_default(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    assert s.get_setting("account_balance", "0") == "0"   # default
    s.set_setting("account_balance", "1000")
    assert s.get_setting("account_balance", "0") == "1000"
    s.set_setting("account_balance", "1500")              # overwrite
    assert s.get_setting("account_balance", "0") == "1500"
    assert s.get_settings()["account_balance"] == "1500"


def test_trade_calls_store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.insert_trade_call({"generated_at": 100, "decision": "long",
                         "entry": 67.4, "rationale": "x", "gates_failed": []})
    s.insert_trade_call({"generated_at": 200, "decision": "no_trade",
                         "gates_failed": ["stale"]})
    latest = s.latest_trade_call()
    assert latest["generated_at"] == 200
    assert latest["decision"] == "no_trade"
    assert latest["gates_failed"] == ["stale"]            # JSON round-trips
    assert len(s.recent_trade_calls(since_ts=0)) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_settings_store.py -v`
Expected: FAIL — `get_setting` missing.

- [ ] **Step 3: Add tables to SCHEMA** — append to the `SCHEMA` string in `db.py` (before its closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS trade_calls (
    generated_at INTEGER PRIMARY KEY,
    decision TEXT,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calls_ts ON trade_calls(generated_at);
```

- [ ] **Step 4: Add Store methods** — add to the `Store` class in `db.py`:

```python
    def get_setting(self, key: str, default=None):
        with self._lock:
            r = self.conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                (key, str(value)))
            self.conn.commit()

    def get_settings(self) -> dict:
        with self._lock:
            rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def insert_trade_call(self, call: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO trade_calls (generated_at, decision, json) "
                "VALUES (?,?,?)",
                (call["generated_at"], call.get("decision"), json.dumps(call)))
            self.conn.commit()

    def latest_trade_call(self):
        with self._lock:
            r = self.conn.execute(
                "SELECT json FROM trade_calls ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()
        return json.loads(r["json"]) if r else None

    def recent_trade_calls(self, since_ts: int) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT json FROM trade_calls WHERE generated_at >= ? "
                "ORDER BY generated_at DESC", (since_ts,)).fetchall()
        return [json.loads(r["json"]) for r in rows]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_settings_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Full suite (no regression)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart pytest -q`
Expected: all prior tests still pass.

---

### Task 5: Decision engine

**Files:**
- Create: `glory-hype/glory_hype/decision/engine.py`
- Test: `glory-hype/tests/test_decision_engine.py`

Context: `record_call(store, judgment)` gathers inputs, runs gates, and — if clear — sizes via the calculator using account/risk/leverage settings, applies the R:R-floor and liq-inside-stop gates, builds + persists the TradeCall.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_decision_engine.py`:

```python
import time
from glory_hype.db import Store
from glory_hype.decision.engine import record_call


def _fresh(store):
    now = int(time.time() * 1000)
    store.insert_ctx({"funding": 0.0001, "open_interest": 1e6, "mark_px": 67.5,
                      "oracle_px": 67.5, "mid_px": 67.5, "premium": 0.0,
                      "prev_day_px": 64.0, "day_ntl_vlm": 1e9}, ts=now)
    store.save_conclusion({"bias": "bullish", "confidence": 0.7, "score": 70,
                           "key_drivers": [], "caution_flags": [],
                           "source_breakdown": {}, "based_on": [], "generated_at": now})
    store.insert_chart_read({"ts": now, "timeframe": "5m", "trend": "range",
                             "current_price": 67.5, "flags": [],
                             "position": {"entry": 67.4, "tp": 68.2, "sl": 66.7},
                             "image_path": None})
    store.set_setting("account_balance", "1000")
    return now


def test_sized_long_call(tmp_path):
    s = Store(str(tmp_path / "e.db"))
    _fresh(s)
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.7, "rationale": "aligned"})
    assert call.decision == "long"
    assert call.margin is not None and call.position_coins is not None
    # risk 1% of 1000 = $10 loss at SL (entry-sl = 0.7) -> coins ~14.28
    assert round(call.position_coins, 2) == round(10 / 0.7, 2)
    assert call.rr is not None
    assert s.latest_trade_call()["decision"] == "long"


def test_gate_blocks_when_chart_flagged(tmp_path):
    s = Store(str(tmp_path / "e2.db"))
    _fresh(s)
    # overwrite chart read with a flagged one
    now = int(time.time() * 1000)
    s.insert_chart_read({"ts": now + 1, "timeframe": "5m", "trend": "range",
                         "current_price": 99.0, "flags": ["diverges 40%"],
                         "position": {"entry": 99, "tp": 100, "sl": 98},
                         "image_path": None})
    call = record_call(s, {"decision": "long", "entry": 99, "tp": 100, "sl": 98,
                           "confidence": 0.9, "rationale": "x"})
    assert call.decision == "no_trade"
    assert any("flag" in g.lower() for g in call.gates_failed)


def test_account_unset_blocks(tmp_path):
    s = Store(str(tmp_path / "e3.db"))
    _fresh(s)
    s.set_setting("account_balance", "0")     # unset
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.7})
    assert call.decision == "no_trade"
    assert any("account" in g.lower() for g in call.gates_failed)


def test_low_rr_blocks(tmp_path):
    s = Store(str(tmp_path / "e4.db"))
    _fresh(s)
    # tp barely above entry, sl far -> R:R < 1
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 67.45, "sl": 66.0,
                           "confidence": 0.7})
    assert call.decision == "no_trade"
    assert any("r:r" in g.lower() or "reward" in g.lower() for g in call.gates_failed)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_decision_engine.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/decision/engine.py`:

```python
"""Decision engine: gather inputs -> hard gates -> size (calculator) -> persist."""

import time

from glory_hype import config
from glory_hype.calc import compute_trade
from glory_hype.decision.gates import evaluate_gates
from glory_hype.decision.tradecall import TradeCall, no_trade, parse_judgment


def record_call(store, judgment: dict) -> TradeCall:
    now = int(time.time() * 1000)
    ctx = store.latest_ctx()
    conclusion = store.latest_conclusion()
    chart_read = store.latest_chart_read()

    gates = evaluate_gates(ctx, conclusion, chart_read, now, config)
    inputs = {"ctx_ts": (ctx or {}).get("ts"),
              "conclusion_at": (conclusion or {}).get("generated_at"),
              "chart_read_ts": (chart_read or {}).get("ts")}
    if gates:
        call = no_trade(gates, now)
        call.inputs = inputs
        store.insert_trade_call(call.to_dict())
        return call

    j = parse_judgment(judgment)
    if j["decision"] == "no_trade":
        call = no_trade([j["rationale"]], now, rationale=j["rationale"])
        call.inputs = inputs
        store.insert_trade_call(call.to_dict())
        return call

    # sizing inputs from settings
    account = float(store.get_setting("account_balance", "0") or 0)
    risk_pct = float(store.get_setting("risk_pct", str(config.DEFAULT_RISK_PCT)))
    leverage = float(store.get_setting("leverage", str(config.DEFAULT_LEVERAGE)))
    if account <= 0:
        call = no_trade(["Set account balance on the dashboard to size the trade."], now)
        call.inputs = inputs
        store.insert_trade_call(call.to_dict())
        return call

    try:
        sized = compute_trade({"mode": "risk_pct", "entry": j["entry"],
                               "tp": j["tp"] if j["tp"] is not None else j["entry"],
                               "sl": j["sl"], "direction": j["decision"],
                               "leverage": leverage, "account": account,
                               "risk_pct": risk_pct})
    except ValueError as e:
        call = no_trade([f"Sizing error: {e}"], now)
        call.inputs = inputs
        store.insert_trade_call(call.to_dict())
        return call

    # post-sizing gates: R:R floor and liquidation inside the stop
    post = []
    rr = sized["rr"]
    if rr is None or rr < config.MIN_RR:
        post.append(f"R:R {rr} below floor {config.MIN_RR}.")
    liq = sized["liq_price"]
    if j["decision"] == "long" and j["sl"] <= liq:
        post.append(f"Liquidation {liq} is at/above the stop {j['sl']}.")
    if j["decision"] == "short" and j["sl"] >= liq:
        post.append(f"Liquidation {liq} is at/below the stop {j['sl']}.")
    if post:
        call = no_trade(post, now)
        call.inputs = inputs
        store.insert_trade_call(call.to_dict())
        return call

    call = TradeCall(
        decision=j["decision"], entry=j["entry"], tp=j["tp"], sl=j["sl"],
        position_notional=sized["position_notional"],
        position_coins=sized["position_coins"], margin=sized["margin"],
        leverage=leverage, rr=rr, liq_price=liq,
        confidence=j["confidence"], rationale=j["rationale"],
        gates_failed=[], inputs=inputs, generated_at=now)
    store.insert_trade_call(call.to_dict())
    return call
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_decision_engine.py -v`
Expected: PASS (4 passed)

---

### Task 6: Server — /api/decision + /api/settings

**Files:**
- Modify: `glory-hype/glory_hype/server.py`
- Test: `glory-hype/tests/test_decision_server.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_decision_server.py`:

```python
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_settings_roundtrip(tmp_path):
    app = create_app(Store(str(tmp_path / "s.db")))
    client = TestClient(app)
    assert client.get("/api/settings").status_code == 200
    r = client.post("/api/settings", json={"account_balance": "2000", "risk_pct": "0.02"})
    assert r.status_code == 200
    got = client.get("/api/settings").json()["settings"]
    assert got["account_balance"] == "2000"
    assert got["risk_pct"] == "0.02"


def test_decision_endpoint_empty(tmp_path):
    app = create_app(Store(str(tmp_path / "d.db")))
    client = TestClient(app)
    r = client.get("/api/decision")
    assert r.status_code == 200
    assert r.json()["call"] is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_decision_server.py -v`
Expected: FAIL — endpoints 404.

- [ ] **Step 3: Implement** — add inside `create_app` in `server.py`, before `return app`:

```python
    @app.get("/api/decision")
    def decision():
        return {"call": store.latest_trade_call()}

    @app.get("/api/settings")
    def get_settings():
        return {"settings": store.get_settings()}

    @app.post("/api/settings")
    def post_settings(body: dict):
        for k, v in body.items():
            store.set_setting(k, v)
        return {"settings": store.get_settings()}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_decision_server.py -v`
Expected: PASS (2 passed)

---

### Task 7: CLI `decide` + dashboard (settings + Decision panel)

**Files:**
- Modify: `glory-hype/glory_hype/__main__.py`
- Modify: `glory-hype/glory_hype/static/index.html`

No new test (thin CLI + static markup); verified by the manual workflow + endpoint tests.

- [ ] **Step 1: Add the `decide` CLI** — in `__main__.py`: add `"decide"` to `choices`, add `from glory_hype.decision.engine import record_call`, and add the branch (the agent passes its judgment as JSON via `--file`):

```python
    elif args.cmd == "decide":
        with open(args.file, encoding="utf-8") as f:
            judgment = _json.load(f)
        call = record_call(store, judgment)
        print(_json.dumps(call.to_dict(), indent=2))
```

- [ ] **Step 2: Add settings inputs + Decision panel** — in `static/index.html`, before `</body>`:

```html
  <h2 style="font-size:14px;margin-top:24px;">Account settings</h2>
  <div class="card" style="font-size:12px;">
    <label>Account $ <input id="s_account" size="8"></label>
    <label>Risk % <input id="s_risk" size="5" placeholder="0.01"></label>
    <label>Leverage <input id="s_lev" size="4" placeholder="10"></label>
    <button id="s_save">Save</button>
    <span id="s_msg" style="color:#26de81;"></span>
  </div>

  <h2 style="font-size:14px;margin-top:24px;">Glory's Decision</h2>
  <div id="decision" class="card">No decision yet.</div>

<script>
function loadSettings(){
  fetch("/api/settings").then(r=>r.json()).then(d=>{
    const s=d.settings||{};
    if(s.account_balance) document.getElementById("s_account").value=s.account_balance;
    if(s.risk_pct) document.getElementById("s_risk").value=s.risk_pct;
    if(s.leverage) document.getElementById("s_lev").value=s.leverage;
  });
}
document.getElementById("s_save").onclick=()=>{
  const body={account_balance:document.getElementById("s_account").value,
    risk_pct:document.getElementById("s_risk").value||"0.01",
    leverage:document.getElementById("s_lev").value||"10"};
  fetch("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)}).then(()=>{document.getElementById("s_msg").textContent="saved";});
};
function renderDecision(d){
  const c=d.call, el=document.getElementById("decision");
  if(!c){ el.textContent="No decision yet."; return; }
  if(c.decision==="no_trade"){
    el.innerHTML=`<div class="val">NO TRADE</div>
      <div class="neg" style="font-size:12px;">${(c.gates_failed||[]).join('<br>')}</div>`;
    return;
  }
  const cls=c.decision==="long"?"pos":"neg";
  el.innerHTML=`<div class="val ${cls}">${c.decision.toUpperCase()} @ ${c.entry}</div>
    <div style="font-size:12px;">TP ${c.tp} &middot; SL ${c.sl} &middot; R:R ${c.rr} &middot; est. liq ${c.liq_price}</div>
    <div style="font-size:12px;">Size: $${c.position_notional} (${c.position_coins} HYPE) &middot; margin $${c.margin} @ ${c.leverage}x</div>
    <div style="font-size:12px;">Confidence ${(c.confidence*100).toFixed(0)}% <span style="color:#8b97a7">(gross, excl. fees)</span></div>
    <div style="font-size:12px;color:#8b97a7;margin-top:4px;">${c.rationale||''}</div>`;
}
function loadDecision(){ fetch("/api/decision").then(r=>r.json()).then(renderDecision); }
loadSettings(); loadDecision(); setInterval(loadDecision, 15000);
</script>
```

- [ ] **Step 3: Run the full offline suite**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart pytest -q`
Expected: ALL green (v1–v4).

- [ ] **Step 4: Manual end-to-end check**

```
cd glory-hype
serve.bat  # http://localhost:5179
# Set account ($1000), risk 0.01, leverage 10 -> Save.
# Agent produces a judgment file and runs:
#   python -m glory_hype decide --file judgment.json
# Decision panel shows the sized call (or NO TRADE + gate reasons).
```

---

### Task 8: Commit (GATED — only after user approval)

> Do NOT run until the user explicitly says to commit.

- [ ] **Step 1: Stage and commit**

```bash
cd E:/Glory
git add glory-hype/glory_hype/decision glory-hype/glory_hype/config.py \
  glory-hype/glory_hype/db.py glory-hype/glory_hype/server.py \
  glory-hype/glory_hype/static/index.html glory-hype/glory_hype/__main__.py \
  glory-hype/tests/test_gates.py glory-hype/tests/test_tradecall.py \
  glory-hype/tests/test_decision_engine.py glory-hype/tests/test_settings_store.py \
  glory-hype/tests/test_decision_server.py glory-hype/tests/test_decision_config.py \
  docs/superpowers/specs/2026-05-30-hype-decision-engine-design.md \
  docs/superpowers/plans/2026-05-30-hype-decision-engine.md
git commit -m "feat(hype): v4 decision engine — gated, sized long/short TradeCall

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Hard gates (missing/stale ctx, missing/stale/unavailable narrative, missing/flagged chart) → Task 2 ✓
- Post-sizing gates (R:R floor, liq inside stop, account unset) → Task 5 ✓
- TradeCall schema + defensive judgment parse → Task 3 ✓
- Agent supplies judgment; code gathers/gates/sizes/persists; gate overrides → Task 5 ✓
- Sizing via calculator risk_pct using DB settings → Task 5 ✓
- Settings in DB + dashboard set → Tasks 4,6,7 ✓
- trade_calls store + /api/decision + dashboard panel → Tasks 4,6,7 ✓
- `decide` CLI → Task 7 ✓
- config thresholds → Task 1 ✓

**Placeholder scan:** No TBD/TODO; complete code in every step; commands have expected output.

**Type consistency:** `record_call(store, judgment)` and `parse_judgment` keys (decision/entry/tp/sl/confidence/rationale) consistent across engine + tradecall + tests. `evaluate_gates(ctx, conclusion, chart_read, now_ms, cfg)` signature consistent (Task 2 & 5). `TradeCall.to_dict()` keys match the dashboard renderer and `/api/decision`. Store methods (`get_setting`/`set_setting`/`get_settings`/`insert_trade_call`/`latest_trade_call`/`recent_trade_calls`) named identically across db/engine/server/tests. `compute_trade` risk_pct inputs match the v3.1 calculator's contract (entry/tp/sl/direction/leverage/account/risk_pct). Reused `latest_ctx`/`latest_conclusion`/`latest_chart_read` already exist from v1–v3.
