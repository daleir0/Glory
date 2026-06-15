# HYPE Autonomous Execution (v6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fire a v4 TradeCall as a real Hyperliquid order (entry + TP + SL bracket) via a non-withdrawing agent wallet, one-click from the dashboard, with every order/fill logged and hard safety rails enforced server-side.

**Architecture:** A `exchange/` subpackage signs orders with a vault-held Hyperliquid agent key (unlocked at startup) using the official `hyperliquid-python-sdk`. Pure `safety.check_rails` gates every fire. `execute_call` re-validates, places the bracket, logs fills. Dashboard adds a Fire button. Real-money paths are tested with a mocked SDK; the only live test is opt-in against Hyperliquid **testnet**.

**Tech Stack:** Python 3.12, `uv`, `hyperliquid-python-sdk` (+`eth_account`), `cryptography` (vault seal — audited primitives, mirrors glory-core), `fastapi`, `pytest`.

> **Git note:** prior work committed through 207ba227. Do NOT commit per-task. Final commit (Task 9) is gated on explicit user approval. **No real mainnet order is ever placed by tests** — only the opt-in testnet `live` smoke, and only the user fires mainnet manually.

Run offline tests with:
`cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography pytest -q`

---

## File Structure

```
glory-hype/glory_hype/
  config.py            # MODIFY: exchange URLs, caps, thresholds
  safety.py            # NEW pure: check_rails(call, live_mark, now, todays_pnl, cfg)
  exchange/
    __init__.py
    keystore.py        # seal/unlock agent key (cryptography); import_agent_key
    hl_client.py       # wrapper over injected hyperliquid Exchange; ExchangeUnreachable
    execute.py         # execute_call(store, client, call, cfg)
  db.py                # MODIFY: orders + fills tables + methods + todays_realized_pnl
  server.py            # MODIFY: /api/execute, /api/orders (client on app.state)
  static/index.html    # MODIFY: Fire button + fill display on Decision panel
  __main__.py          # MODIFY: import-key CLI; serve unlocks vault at startup
  tests/
    test_safety.py
    test_keystore.py
    test_hl_client.py
    test_execute.py
    test_orders_store.py
    test_execute_server.py
    test_smoke_execution_live.py   # opt-in testnet only
```

---

### Task 1: Config — exchange URLs, caps, thresholds

**Files:**
- Modify: `glory-hype/glory_hype/config.py`
- Test: `glory-hype/tests/test_safety.py` (config assertions folded into Task 2)

- [ ] **Step 1: Append to `glory-hype/glory_hype/config.py`**

```python
# --- v6 execution ---
HL_MAINNET_URL = "https://api.hyperliquid.xyz"
HL_TESTNET_URL = "https://api.hyperliquid-testnet.xyz"
EXEC_FRESH_MS = 5 * 60 * 1000      # call must be < 5 min old to fire
EXEC_DRIFT_PCT = 1.0               # live mark within 1% of entry
MAX_POSITION_USD = 200.0           # hard cap on a single position notional
DAILY_LOSS_CAP_USD = 50.0          # stop firing once today's realized losses hit this
VAULT_PATH = "agent.vault"         # sealed agent key location
```

- [ ] **Step 2: Verify import**

Run: `cd glory-hype && uv run python -c "from glory_hype import config; print(config.MAX_POSITION_USD, config.HL_MAINNET_URL)"`
Expected: `200.0 https://api.hyperliquid.xyz`

---

### Task 2: Safety rails (pure)

**Files:**
- Create: `glory-hype/glory_hype/safety.py`
- Test: `glory-hype/tests/test_safety.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_safety.py`:

```python
from glory_hype import config
from glory_hype.safety import check_rails

NOW = 1_000_000_000_000


def _call(entry=100.0, notional=150.0, gen=NOW):
    return {"decision": "long", "entry": entry, "tp": 110.0, "sl": 95.0,
            "position_notional": notional, "generated_at": gen}


def test_all_clear():
    assert check_rails(_call(), 100.3, NOW, 0.0, config) == []


def test_stale_call():
    old = NOW - config.EXEC_FRESH_MS - 1
    r = check_rails(_call(gen=old), 100.0, NOW, 0.0, config)
    assert any("stale" in x.lower() or "old" in x.lower() for x in r)


def test_price_drift():
    r = check_rails(_call(entry=100.0), 102.0, NOW, 0.0, config)  # 2% > 1%
    assert any("drift" in x.lower() or "moved" in x.lower() for x in r)


def test_over_max_position():
    r = check_rails(_call(notional=500.0), 100.0, NOW, 0.0, config)  # > 200
    assert any("position" in x.lower() and "cap" in x.lower() for x in r)


def test_daily_loss_cap():
    r = check_rails(_call(), 100.0, NOW, -config.DAILY_LOSS_CAP_USD, config)
    assert any("loss cap" in x.lower() for x in r)


def test_no_trade_call_blocked():
    c = _call(); c["decision"] = "no_trade"
    r = check_rails(c, 100.0, NOW, 0.0, config)
    assert any("no_trade" in x.lower() or "not actionable" in x.lower() for x in r)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_safety.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/safety.py`:

```python
"""Pure pre-execution safety rails. Any returned reason blocks the fire."""


def check_rails(call, live_mark, now_ms, todays_realized_pnl, cfg) -> list:
    reasons = []
    if call.get("decision") not in ("long", "short"):
        reasons.append("Call is not actionable (no_trade).")
        return reasons
    entry = call.get("entry")
    notional = call.get("position_notional") or 0.0

    if now_ms - call.get("generated_at", 0) > cfg.EXEC_FRESH_MS:
        reasons.append("Call is stale (older than the freshness window).")
    if entry and live_mark:
        drift = abs(live_mark - entry) / entry * 100
        if drift > cfg.EXEC_DRIFT_PCT:
            reasons.append(f"Price moved {drift:.2f}% from entry (drift cap "
                           f"{cfg.EXEC_DRIFT_PCT}%).")
    if notional > cfg.MAX_POSITION_USD:
        reasons.append(f"Position ${notional} exceeds max position cap "
                       f"${cfg.MAX_POSITION_USD}.")
    if todays_realized_pnl <= -cfg.DAILY_LOSS_CAP_USD:
        reasons.append(f"Daily loss cap hit (${todays_realized_pnl} realized today).")
    return reasons
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_safety.py -v`
Expected: PASS (6 passed)

---

### Task 3: Keystore — seal/unlock the agent key

**Files:**
- Create: `glory-hype/glory_hype/exchange/__init__.py`, `glory-hype/glory_hype/exchange/keystore.py`
- Test: `glory-hype/tests/test_keystore.py`

Context: stores `{"key": "0x..", "address": "0x.."}` encrypted with ChaCha20-Poly1305, key derived from passphrase via Scrypt (both from the audited `cryptography` lib — not home-rolled). Mirrors glory-core's primitives; kept in-package to avoid cross-project install fragility.

- [ ] **Step 1: Create the package init**

`glory-hype/glory_hype/exchange/__init__.py`:

```python
"""HYPE execution (v6): vault-held agent key + Hyperliquid order signing."""
```

- [ ] **Step 2: Write the failing test**

`glory-hype/tests/test_keystore.py`:

```python
import pytest
from glory_hype.exchange.keystore import import_agent_key, unlock


def test_seal_unlock_roundtrip(tmp_path):
    path = str(tmp_path / "agent.vault")
    import_agent_key("0xabc123", "0xMAIN", "passphrase123", path)
    key, addr = unlock("passphrase123", path)
    assert key == "0xabc123"
    assert addr == "0xMAIN"


def test_wrong_passphrase_fails(tmp_path):
    path = str(tmp_path / "agent.vault")
    import_agent_key("0xabc123", "0xMAIN", "right", path)
    with pytest.raises(Exception):
        unlock("wrong", path)


def test_missing_vault_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        unlock("x", str(tmp_path / "nope.vault"))
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with cryptography pytest tests/test_keystore.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement**

`glory-hype/glory_hype/exchange/keystore.py`:

```python
"""Seal/unlock the Hyperliquid agent key with audited authenticated encryption.

Layout on disk: salt(16) | nonce(12) | ciphertext. Key derived via Scrypt."""

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_SALT = 16
_NONCE = 12


def _derive(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1)
    return kdf.derive(passphrase.encode())


def import_agent_key(agent_key_hex: str, main_address: str,
                     passphrase: str, path: str) -> None:
    blob = json.dumps({"key": agent_key_hex, "address": main_address}).encode()
    salt = os.urandom(_SALT)
    nonce = os.urandom(_NONCE)
    ct = ChaCha20Poly1305(_derive(passphrase, salt)).encrypt(nonce, blob, None)
    Path(path).write_bytes(salt + nonce + ct)


def unlock(passphrase: str, path: str):
    raw = Path(path).read_bytes()
    salt, nonce, ct = raw[:_SALT], raw[_SALT:_SALT + _NONCE], raw[_SALT + _NONCE:]
    blob = ChaCha20Poly1305(_derive(passphrase, salt)).decrypt(nonce, ct, None)
    d = json.loads(blob)
    return d["key"], d["address"]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest --with cryptography pytest tests/test_keystore.py -v`
Expected: PASS (3 passed)

---

### Task 4: Orders + fills store

**Files:**
- Modify: `glory-hype/glory_hype/db.py`
- Test: `glory-hype/tests/test_orders_store.py`

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_orders_store.py`:

```python
import time
from glory_hype.db import Store


def test_orders_and_fills(tmp_path):
    s = Store(str(tmp_path / "o.db"))
    s.insert_order({"id": "oid1", "call_at": 1000, "ts": 1100, "type": "limit",
                    "side": "buy", "px": 100.0, "sz": 1.0, "reduce_only": False,
                    "status": "resting", "raw_json": "{}"})
    assert s.recent_orders(limit=10)[0]["id"] == "oid1"
    s.insert_fill({"tid": "t1", "order_id": "oid1", "ts": 1200, "px": 100.0,
                   "sz": 1.0, "fee": 0.05, "closed_pnl": 0.0, "raw_json": "{}"})
    s.insert_fill({"tid": "t2", "order_id": "oid1", "ts": 1300, "px": 101.0,
                   "sz": 1.0, "fee": 0.05, "closed_pnl": -3.0, "raw_json": "{}"})
    assert s.recent_orders(limit=10)[0]["id"] == "oid1"


def test_todays_realized_pnl(tmp_path):
    s = Store(str(tmp_path / "o2.db"))
    now = int(time.time() * 1000)
    s.insert_fill({"tid": "a", "order_id": "o", "ts": now, "px": 1, "sz": 1,
                   "fee": 0.0, "closed_pnl": -5.0, "raw_json": "{}"})
    s.insert_fill({"tid": "b", "order_id": "o", "ts": now, "px": 1, "sz": 1,
                   "fee": 0.0, "closed_pnl": 2.0, "raw_json": "{}"})
    # old fill (2 days ago) must be excluded
    s.insert_fill({"tid": "c", "order_id": "o", "ts": now - 2 * 86400_000, "px": 1,
                   "sz": 1, "fee": 0.0, "closed_pnl": -100.0, "raw_json": "{}"})
    assert s.todays_realized_pnl() == -3.0    # -5 + 2, old excluded
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_orders_store.py -v`
Expected: FAIL — `insert_order` missing.

- [ ] **Step 3: Add tables to SCHEMA** — append to the `SCHEMA` string in `db.py`:

```sql
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    call_at INTEGER, ts INTEGER, type TEXT, side TEXT,
    px REAL, sz REAL, reduce_only INTEGER, status TEXT, raw_json TEXT
);
CREATE TABLE IF NOT EXISTS fills (
    tid TEXT PRIMARY KEY,
    order_id TEXT, ts INTEGER, px REAL, sz REAL, fee REAL,
    closed_pnl REAL, raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_ts ON orders(ts);
CREATE INDEX IF NOT EXISTS idx_fills_ts ON fills(ts);
```

- [ ] **Step 4: Add methods to `Store`** (in `db.py`):

```python
    def insert_order(self, o: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO orders
                   (id, call_at, ts, type, side, px, sz, reduce_only, status, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (o["id"], o.get("call_at"), o.get("ts"), o.get("type"), o.get("side"),
                 o.get("px"), o.get("sz"), 1 if o.get("reduce_only") else 0,
                 o.get("status"), o.get("raw_json", "{}")))
            self.conn.commit()

    def insert_fill(self, f: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO fills
                   (tid, order_id, ts, px, sz, fee, closed_pnl, raw_json)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (f["tid"], f.get("order_id"), f.get("ts"), f.get("px"), f.get("sz"),
                 f.get("fee"), f.get("closed_pnl"), f.get("raw_json", "{}")))
            self.conn.commit()

    def recent_orders(self, limit: int = 20) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM orders ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def recent_fills(self, limit: int = 50) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM fills ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def todays_realized_pnl(self) -> float:
        import time
        midnight = int((time.time() // 86400) * 86400 * 1000)
        with self._lock:
            r = self.conn.execute(
                "SELECT COALESCE(SUM(closed_pnl),0) AS p FROM fills WHERE ts >= ?",
                (midnight,)).fetchone()
        return float(r["p"])
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_orders_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Full suite (no regression)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography pytest -q`
Expected: all prior pass.

---

### Task 5: Hyperliquid client wrapper

**Files:**
- Create: `glory-hype/glory_hype/exchange/hl_client.py`
- Test: `glory-hype/tests/test_hl_client.py`

Context: thin wrapper over an **injected** exchange object (the `hyperliquid.exchange.Exchange` in production, a fake in tests). Translates intent → SDK calls; normalizes responses; raises `ExchangeUnreachable` on network failure. We inject the exchange so no real SDK/network is touched in unit tests.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_hl_client.py`:

```python
import pytest
from glory_hype.exchange.hl_client import HLClient, ExchangeUnreachable


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, name, is_buy, sz, limit_px, order_type, reduce_only=False):
        self.calls.append(("order", name, is_buy, sz, limit_px, order_type, reduce_only))
        return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": 7}}]}}}

    def market_open(self, name, is_buy, sz):
        self.calls.append(("market_open", name, is_buy, sz))
        return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"oid": 9, "avgPx": "100.0", "totalSz": str(sz)}}]}}}


def test_limit_order_builds_gtc():
    fx = FakeExchange()
    c = HLClient(fx, coin="HYPE")
    r = c.limit_order(is_buy=True, px=100.0, sz=1.5, tif="Gtc")
    name, is_buy, sz, px, otype, ro = fx.calls[0][1:]
    assert name == "HYPE" and is_buy is True and sz == 1.5 and px == 100.0
    assert otype == {"limit": {"tif": "Gtc"}} and ro is False
    assert r["status"] == "ok"


def test_market_open():
    fx = FakeExchange()
    c = HLClient(fx, coin="HYPE")
    c.market_open(is_buy=False, sz=2.0)
    assert fx.calls[0][0] == "market_open"


def test_trigger_order_reduce_only():
    fx = FakeExchange()
    c = HLClient(fx, coin="HYPE")
    c.trigger_order(is_buy=False, trigger_px=95.0, sz=1.0, is_tp=False)
    otype = fx.calls[0][5]
    assert "trigger" in otype
    assert otype["trigger"]["triggerPx"] == 95.0
    assert otype["trigger"]["tpsl"] == "sl"
    assert fx.calls[0][6] is True   # reduce_only


def test_network_error_wrapped():
    class Boom:
        def order(self, *a, **k): raise OSError("conn refused")
    c = HLClient(Boom(), coin="HYPE")
    with pytest.raises(ExchangeUnreachable):
        c.limit_order(is_buy=True, px=1.0, sz=1.0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_hl_client.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/exchange/hl_client.py`:

```python
"""Wrapper over the Hyperliquid SDK Exchange. Injected for testability."""


class ExchangeUnreachable(Exception):
    pass


class HLClient:
    def __init__(self, exchange, coin: str = "HYPE"):
        self.ex = exchange
        self.coin = coin

    def _guard(self, fn, *a, **k):
        try:
            return fn(*a, **k)
        except ExchangeUnreachable:
            raise
        except (OSError, ConnectionError, TimeoutError) as e:
            raise ExchangeUnreachable(
                f"exchange unreachable ({e}) — is the VPN running?") from e

    def limit_order(self, is_buy: bool, px: float, sz: float, tif: str = "Gtc",
                    reduce_only: bool = False):
        return self._guard(self.ex.order, self.coin, is_buy, sz, px,
                           {"limit": {"tif": tif}}, reduce_only=reduce_only)

    def market_open(self, is_buy: bool, sz: float):
        return self._guard(self.ex.market_open, self.coin, is_buy, sz)

    def market_close(self):
        return self._guard(self.ex.market_close, self.coin)

    def trigger_order(self, is_buy: bool, trigger_px: float, sz: float,
                      is_tp: bool, reduce_only: bool = True):
        otype = {"trigger": {"triggerPx": trigger_px, "isMarket": True,
                             "tpsl": "tp" if is_tp else "sl"}}
        return self._guard(self.ex.order, self.coin, is_buy, sz, trigger_px,
                           otype, reduce_only=reduce_only)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_hl_client.py -v`
Expected: PASS (4 passed)

---

### Task 6: execute_call orchestration

**Files:**
- Create: `glory-hype/glory_hype/exchange/execute.py`
- Test: `glory-hype/tests/test_execute.py`

Context: re-gate against live data, then place the bracket (entry + TP + SL), logging each order. Uses an injected `HLClient`-shaped object so tests never touch the network.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_execute.py`:

```python
import time
from glory_hype.db import Store
from glory_hype.exchange.execute import execute_call
from glory_hype import config


class FakeClient:
    def __init__(self):
        self.orders = []

    def market_open(self, is_buy, sz):
        self.orders.append(("market_open", is_buy, sz))
        return {"response": {"data": {"statuses": [{"filled": {"oid": 1, "avgPx": "100.0", "totalSz": str(sz)}}]}}}

    def limit_order(self, is_buy, px, sz, tif="Gtc", reduce_only=False):
        self.orders.append(("limit", is_buy, px, sz, reduce_only))
        return {"response": {"data": {"statuses": [{"resting": {"oid": 2}}]}}}

    def trigger_order(self, is_buy, trigger_px, sz, is_tp, reduce_only=True):
        self.orders.append(("trigger", is_buy, trigger_px, sz, is_tp))
        return {"response": {"data": {"statuses": [{"resting": {"oid": 3}}]}}}


def _seed(store, entry=100.0):
    now = int(time.time() * 1000)
    store.insert_ctx({"funding": 0.0, "open_interest": 1.0, "mark_px": entry,
                      "oracle_px": entry, "mid_px": entry, "premium": 0.0,
                      "prev_day_px": entry, "day_ntl_vlm": 1.0}, ts=now)
    return now


def _call(now, entry=100.0, notional=150.0):
    return {"decision": "long", "entry": entry, "tp": 110.0, "sl": 95.0,
            "position_notional": notional, "position_coins": 1.5,
            "generated_at": now}


def test_execute_places_bracket(tmp_path):
    s = Store(str(tmp_path / "x.db"))
    now = _seed(s)
    fc = FakeClient()
    res = execute_call(s, fc, _call(now), config)
    assert res["status"] == "filled"
    kinds = [o[0] for o in fc.orders]
    assert "market_open" in kinds          # entry (at mark)
    assert kinds.count("trigger") == 2     # TP + SL
    assert len(s.recent_orders()) >= 3     # logged


def test_execute_blocked_by_rail(tmp_path):
    s = Store(str(tmp_path / "x2.db"))
    now = _seed(s, entry=100.0)
    fc = FakeClient()
    call = _call(now, notional=999.0)      # over max position
    res = execute_call(s, fc, call, config)
    assert res["status"] == "blocked"
    assert fc.orders == []                  # nothing placed
    assert any("cap" in r.lower() for r in res["reasons"])


def test_execute_stale_call_blocked(tmp_path):
    s = Store(str(tmp_path / "x3.db"))
    now = _seed(s)
    fc = FakeClient()
    old = now - config.EXEC_FRESH_MS - 1
    res = execute_call(s, fc, _call(old), config)
    assert res["status"] == "blocked"
    assert fc.orders == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_execute.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/exchange/execute.py`:

```python
"""Execute a TradeCall as a bracket order (entry + TP + SL) with re-gating."""

import json
import time

from glory_hype.safety import check_rails


def _oid(resp):
    try:
        st = resp["response"]["data"]["statuses"][0]
        return str((st.get("filled") or st.get("resting"))["oid"])
    except Exception:
        return f"unknown-{int(time.time()*1000)}"


def execute_call(store, client, call, cfg) -> dict:
    now = int(time.time() * 1000)
    ctx = store.latest_ctx()
    live_mark = ctx.get("mark_px") if ctx else None
    reasons = check_rails(call, live_mark, now, store.todays_realized_pnl(), cfg)
    if not live_mark:
        reasons.append("No live mark to validate against.")
    if reasons:
        return {"status": "blocked", "reasons": reasons}

    is_buy = call["decision"] == "long"
    coins = call["position_coins"]
    placed = []

    # 1) entry — market (rails already confirmed mark within drift of entry)
    entry_resp = client.market_open(is_buy=is_buy, sz=coins)
    store.insert_order({"id": _oid(entry_resp), "call_at": call["generated_at"],
                        "ts": now, "type": "market", "side": "buy" if is_buy else "sell",
                        "px": call["entry"], "sz": coins, "reduce_only": False,
                        "status": "filled", "raw_json": json.dumps(entry_resp)})
    placed.append("entry")

    # 2) TP + 3) SL — reduce-only triggers, opposite side
    if call.get("tp") is not None:
        tp_resp = client.trigger_order(is_buy=not is_buy, trigger_px=call["tp"],
                                       sz=coins, is_tp=True)
        store.insert_order({"id": _oid(tp_resp), "call_at": call["generated_at"],
                            "ts": now, "type": "trigger", "side": "sell" if is_buy else "buy",
                            "px": call["tp"], "sz": coins, "reduce_only": True,
                            "status": "resting", "raw_json": json.dumps(tp_resp)})
        placed.append("tp")
    if call.get("sl") is not None:
        sl_resp = client.trigger_order(is_buy=not is_buy, trigger_px=call["sl"],
                                       sz=coins, is_tp=False)
        store.insert_order({"id": _oid(sl_resp), "call_at": call["generated_at"],
                            "ts": now, "type": "trigger", "side": "sell" if is_buy else "buy",
                            "px": call["sl"], "sz": coins, "reduce_only": True,
                            "status": "resting", "raw_json": json.dumps(sl_resp)})
        placed.append("sl")

    return {"status": "filled", "placed": placed,
            "orders": store.recent_orders(limit=5)}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_execute.py -v`
Expected: PASS (3 passed)

---

### Task 7: Server endpoints + CLI import-key/startup unlock + dashboard Fire

**Files:**
- Modify: `glory-hype/glory_hype/server.py`, `glory-hype/glory_hype/__main__.py`, `glory-hype/glory_hype/static/index.html`
- Test: `glory-hype/tests/test_execute_server.py`

- [ ] **Step 1: Write the failing server test**

`glory-hype/tests/test_execute_server.py`:

```python
import time
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


class FakeClient:
    def market_open(self, is_buy, sz):
        return {"response": {"data": {"statuses": [{"filled": {"oid": 1, "avgPx": "100.0", "totalSz": str(sz)}}]}}}
    def trigger_order(self, is_buy, trigger_px, sz, is_tp, reduce_only=True):
        return {"response": {"data": {"statuses": [{"resting": {"oid": 2}}]}}}


def _seed(store):
    now = int(time.time() * 1000)
    store.insert_ctx({"funding": 0.0, "open_interest": 1.0, "mark_px": 100.0,
                      "oracle_px": 100.0, "mid_px": 100.0, "premium": 0.0,
                      "prev_day_px": 100.0, "day_ntl_vlm": 1.0}, ts=now)
    store.insert_trade_call({"generated_at": now, "decision": "long", "entry": 100.0,
                             "tp": 110.0, "sl": 95.0, "position_notional": 150.0,
                             "position_coins": 1.5})
    return now


def test_execute_endpoint_fires(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    _seed(s)
    app = create_app(s, hl_client=FakeClient())
    client = TestClient(app)
    r = client.post("/api/execute")
    assert r.status_code == 200
    assert r.json()["status"] == "filled"
    assert len(client.get("/api/orders").json()["orders"]) >= 3


def test_execute_no_client_returns_locked(tmp_path):
    s = Store(str(tmp_path / "s2.db"))
    _seed(s)
    app = create_app(s)                      # no client injected = vault not unlocked
    client = TestClient(app)
    r = client.post("/api/execute")
    assert r.status_code == 409
    assert "unlock" in r.json()["detail"].lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_execute_server.py -v`
Expected: FAIL — `create_app` has no `hl_client` param / `/api/execute` 404.

- [ ] **Step 3: Update `create_app` + endpoints** in `server.py`.

Change the signature and store the client:

```python
def create_app(store: Store, charts_dir: str = _DEFAULT_CHARTS_DIR, hl_client=None) -> FastAPI:
```

Add near the other imports:

```python
from glory_hype.exchange.execute import execute_call
from glory_hype.exchange.hl_client import ExchangeUnreachable
from glory_hype import config as _cfg
```

Add inside `create_app`, before `return app`:

```python
    app.state.hl_client = hl_client

    @app.post("/api/execute")
    def execute():
        client = app.state.hl_client
        if client is None:
            raise HTTPException(status_code=409,
                                detail="Agent key not unlocked — start the server with the vault passphrase.")
        call = store.latest_trade_call()
        if not call or call.get("decision") not in ("long", "short"):
            raise HTTPException(status_code=409, detail="No actionable trade call to fire.")
        try:
            return execute_call(store, client, call, _cfg)
        except ExchangeUnreachable as e:
            raise HTTPException(status_code=503, detail=str(e))

    @app.get("/api/orders")
    def orders():
        return {"orders": store.recent_orders(20), "fills": store.recent_fills(50)}
```

- [ ] **Step 4: Run server test to pass**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_execute_server.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Add import-key CLI + startup unlock** in `__main__.py`.

Add imports:

```python
from glory_hype.exchange.keystore import import_agent_key, unlock
```

Add `"import-key"` to the `choices` list. Add a `--main-address` arg near the others:

```python
    p.add_argument("--main-address", help="main Hyperliquid account address (for import-key)")
```

Add the `import-key` branch (uses getpass; never echoes secrets):

```python
    elif args.cmd == "import-key":
        import getpass
        agent_key = getpass.getpass("Agent private key (0x...): ").strip()
        addr = args.main_address or input("Main account address (0x...): ").strip()
        pw = getpass.getpass("Vault passphrase: ")
        import_agent_key(agent_key, addr, pw, config.VAULT_PATH)
        print("Agent key sealed to", config.VAULT_PATH)
        return
```

Change the `serve` branch to unlock the vault and build the live client. Replace the existing `serve` branch body with:

```python
    elif args.cmd == "serve":
        hl_client = None
        import os
        if os.path.exists(config.VAULT_PATH):
            import getpass
            from eth_account import Account
            from hyperliquid.exchange import Exchange
            from glory_hype.exchange.hl_client import HLClient
            pw = getpass.getpass("Vault passphrase (blank to run read-only): ")
            if pw:
                key, addr = unlock(pw, config.VAULT_PATH)
                ex = Exchange(Account.from_key(key), config.HL_MAINNET_URL,
                              account_address=addr)
                hl_client = HLClient(ex, coin=config.COIN)
                print("Agent key unlocked — execution enabled.")
        uvicorn.run(create_app(store, hl_client=hl_client), host="0.0.0.0", port=args.port)
```

- [ ] **Step 6: Add the Fire button** to `static/index.html` — inside the Decision panel renderer, after the rationale line in `renderDecision` (only for actionable calls):

```html
```
Add to `renderDecision(d)`'s actionable branch (where it builds the long/short innerHTML), append a button + result div:

```javascript
  el.innerHTML += `<button id="fireBtn" style="margin-top:8px;background:#26de81;
    color:#0b0e11;font-weight:bold;border:none;border-radius:6px;padding:6px 14px;
    cursor:pointer;">🔥 Fire ${c.decision.toUpperCase()}</button>
    <span id="fireMsg" style="margin-left:8px;font-size:12px;"></span>`;
  const btn = document.getElementById("fireBtn");
  if (btn) btn.onclick = () => {
    document.getElementById("fireMsg").textContent = "firing…";
    fetch("/api/execute", {method:"POST"}).then(async r=>{
      const m = document.getElementById("fireMsg");
      const body = await r.json();
      if (!r.ok){ m.innerHTML = '<span class="neg">'+(body.detail||'blocked')+'</span>'; return; }
      if (body.status === "blocked"){
        m.innerHTML = '<span class="neg">BLOCKED: '+body.reasons.join('; ')+'</span>'; return;
      }
      m.innerHTML = '<span class="pos">FILLED ('+(body.placed||[]).join('+')+')</span>';
    }).catch(()=>{ document.getElementById("fireMsg").innerHTML='<span class="neg">error</span>'; });
  };
```

- [ ] **Step 7: requirements + pyproject** — add to `requirements.txt`:

```
hyperliquid-python-sdk>=0.9
cryptography>=42.0
```

and add both to `dependencies` in `pyproject.toml`.

- [ ] **Step 8: Full offline suite**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography pytest -q`
Expected: ALL green (v1–v6 offline).

---

### Task 8: Testnet live smoke (opt-in, never mainnet)

**Files:**
- Create: `glory-hype/tests/test_smoke_execution_live.py`

- [ ] **Step 1: Write the testnet smoke** (requires a testnet agent key in env; skipped otherwise)

`glory-hype/tests/test_smoke_execution_live.py`:

```python
import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("HL_TESTNET_KEY"),
                    reason="set HL_TESTNET_KEY + HL_TESTNET_ADDR to run")
def test_testnet_place_and_cancel():
    """Real TESTNET order: place a far-from-mark limit, confirm it rests, cancel it.
    Never runs against mainnet; never touches real funds."""
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from glory_hype import config
    from glory_hype.exchange.hl_client import HLClient

    key = os.environ["HL_TESTNET_KEY"]
    addr = os.environ["HL_TESTNET_ADDR"]
    ex = Exchange(Account.from_key(key), config.HL_TESTNET_URL, account_address=addr)
    c = HLClient(ex, coin="HYPE")
    # buy limit far below mark so it rests (won't fill), then we know signing works
    resp = c.limit_order(is_buy=True, px=1.0, sz=1.0, tif="Gtc")
    assert resp.get("status") == "ok" or "response" in resp
    # cancel everything we just placed
    info = Info(config.HL_TESTNET_URL)
    open_orders = info.open_orders(addr)
    for o in open_orders:
        ex.cancel("HYPE", o["oid"])
```

- [ ] **Step 2: Offline suite still green (live deselected)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser --with python-multipart --with cryptography pytest -q`
Expected: PASS; live deselected.

- [ ] **Step 3: (Manual, user-run) testnet smoke** — only when the user has a testnet key:

Run: `cd glory-hype && HL_TESTNET_KEY=0x.. HL_TESTNET_ADDR=0x.. uv run --with pytest --with hyperliquid-python-sdk pytest -m live tests/test_smoke_execution_live.py -v`
Expected: places + cancels a resting testnet order; proves signing end-to-end.

---

### Task 9: Commit (GATED — only after user approval)

> Do NOT run until the user explicitly says to commit.

- [ ] **Step 1: Stage and commit**

```bash
cd E:/Glory
git add glory-hype docs/superpowers/specs/2026-05-31-hype-execution-design.md \
  docs/superpowers/plans/2026-05-31-hype-execution.md
git commit -m "feat(hype): v6 autonomous execution — agent-wallet orders, one-click fire, safety rails

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Agent-wallet signing via hyperliquid-python-sdk → Task 5, 7 (serve builds Exchange from agent key) ✓
- Vault import + startup unlock → Task 3 (keystore), Task 7 (import-key CLI, serve unlock) ✓
- All order types (market/limit/trigger, reduce-only) → Task 5 ✓
- Bracket execution (entry+TP+SL) → Task 6 ✓
- Safety rails (freshness/drift/max-size/daily-loss) → Task 2, enforced in Task 6 ✓
- Order/fill logging + todays_realized_pnl → Task 4 ✓
- /api/execute + /api/orders + Fire button → Task 7 ✓
- VPN/unreachable handling → Task 5 (ExchangeUnreachable) + Task 7 (503) ✓
- Testnet-only live test → Task 8 ✓
- Out of scope (v7/v8, trailing, unattended) → not built ✓

**Placeholder scan:** No TBD/TODO; complete code in every step; commands have expected output.

**Type consistency:** `check_rails(call, live_mark, now_ms, todays_realized_pnl, cfg)` consistent across safety/execute/server. `HLClient` methods (`limit_order`/`market_open`/`market_close`/`trigger_order`) match the fakes in test_execute and test_execute_server. `execute_call(store, client, call, cfg)` signature consistent. Store methods (`insert_order`/`insert_fill`/`recent_orders`/`recent_fills`/`todays_realized_pnl`) named identically across db/execute/server/tests. `keystore.import_agent_key`/`unlock` signatures consistent across keystore/CLI. `create_app(store, charts_dir, hl_client)` matches the execute-server test. Order dict keys (`id/call_at/ts/type/side/px/sz/reduce_only/status/raw_json`) consistent between execute and the store.

**Deliberate spec deviation (flagged):** keystore uses the audited `cryptography` lib in-package (ChaCha20-Poly1305 + Scrypt) rather than importing `glory-core`, to avoid cross-project uv-install fragility. Same primitive class, no home-rolled crypto. Swappable to glory-core later.

**Real-money safeguards verified in plan:** no test places a mainnet order; the only live test is testnet + skipped without explicit env keys; rails are re-checked at execution time (Task 6) not just at call time; agent wallet cannot withdraw (architectural).
