# HYPE Chart Reader (v3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a structured `ChartRead` (everything visible on a pasted HYPE chart) into the v1 `hype.db` timeline, with the screenshot saved for learning and a dashboard panel — the third input to v4.

**Architecture:** A `chart/` subpackage in `glory-hype`. The Claude Code agent is the vision engine (reads the pasted image, produces ChartRead JSON); v3's code is a defensive parser + storage + display. Mirrors the v2 conclusion/store/server/CLI patterns exactly.

**Tech Stack:** Python 3.12, `uv`, stdlib `sqlite3`/`json`, `fastapi`, `pytest`. No new dependencies.

> **Git note:** v1+v2 are already committed (c814cc4f). Do NOT commit per-task. Final commit is a gated task requiring explicit user approval.

Run offline tests with:
`cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser pytest -q`

---

## File Structure

```
glory-hype/
  .gitignore                       # MODIFY: ignore charts/
  glory_hype/
    chart/
      __init__.py
      chartread.py     # ChartRead dataclass + parse_chart_read (defensive) + to_dict
      record.py        # record_chart_read(store, data, image_bytes=None) -> ChartRead
    db.py              # MODIFY: add chart_reads table + 3 Store methods
    server.py          # MODIFY: add /api/chart
    static/index.html  # MODIFY: add Chart panel
    __main__.py        # MODIFY: add `chart` subcommand
    charts/            # created at runtime by record_chart_read (gitignored)
  tests/
    test_chartread.py
    test_chart_store.py
    test_chart_record.py
    test_chart_server.py
```

---

### Task 1: ChartRead schema + defensive parser

**Files:**
- Create: `glory-hype/glory_hype/chart/__init__.py`
- Create: `glory-hype/glory_hype/chart/chartread.py`
- Test: `glory-hype/tests/test_chartread.py`

Context: mirrors `narrative/conclusion.py` — a dataclass plus a defensive `parse_chart_read` that coerces types, defaults missing fields, and drops non-numeric levels so a sloppy extraction never corrupts a row.

- [ ] **Step 1: Create the package init**

`glory-hype/glory_hype/chart/__init__.py`:

```python
"""HYPE chart reader (v3): structured ChartRead from a pasted chart image."""
```

- [ ] **Step 2: Write the failing test**

`glory-hype/tests/test_chartread.py`:

```python
from glory_hype.chart.chartread import ChartRead, parse_chart_read


def test_parse_full():
    data = {
        "timeframe": "1h", "exchange_pair": "Hyperliquid HYPE-USD",
        "price_range_low": 60.0, "price_range_high": 67.0,
        "current_price": 65.6, "swing_high": 66.84, "swing_low": 61.9,
        "trend": "up", "support_levels": [64.0, 62.0],
        "resistance_levels": [66.8], "patterns": ["ascending triangle"],
        "signals": ["bullish engulfing"], "indicators": {"rsi": 68.0},
        "position": {"side": "long", "entry": 63.0}, "orders": ["TP 70"],
        "annotations": ["trendline from 58"], "visible_text": ["HYPE", "Perp"],
        "notes": "uptrend, extended",
    }
    c = parse_chart_read(data, ts=1000, image_path="charts/x.png")
    assert c.timeframe == "1h"
    assert c.current_price == 65.6
    assert c.trend == "up"
    assert c.support_levels == [64.0, 62.0]
    assert c.indicators["rsi"] == 68.0
    assert c.position["side"] == "long"
    assert c.image_path == "charts/x.png"
    assert c.ts == 1000
    assert c.raw == data


def test_parse_partial_defaults():
    c = parse_chart_read({"current_price": 65.0}, ts=5, image_path=None)
    assert c.timeframe == "unknown"
    assert c.trend == "unknown"
    assert c.support_levels == []
    assert c.resistance_levels == []
    assert c.patterns == []
    assert c.indicators == {}
    assert c.position is None
    assert c.current_price == 65.0
    assert c.swing_high is None


def test_parse_drops_non_numeric_levels():
    c = parse_chart_read(
        {"support_levels": [64.0, "n/a", None, 62.5], "resistance_levels": "67"},
        ts=1, image_path=None)
    assert c.support_levels == [64.0, 62.5]
    assert c.resistance_levels == []   # non-list -> empty


def test_parse_garbage_is_safe():
    c = parse_chart_read({"trend": 123, "current_price": "not-a-number"},
                         ts=9, image_path=None)
    assert c.trend == "unknown"        # non-str/invalid -> unknown
    assert c.current_price is None     # uncoercible -> None
    assert isinstance(c.to_dict(), dict)


def test_to_dict_roundtrips_collections():
    c = parse_chart_read({"patterns": ["flag"], "indicators": {"rsi": 70}},
                         ts=2, image_path=None)
    d = c.to_dict()
    assert d["patterns"] == ["flag"]
    assert d["indicators"] == {"rsi": 70}
    assert d["ts"] == 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chartread.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'glory_hype.chart.chartread'`

- [ ] **Step 4: Implement**

`glory-hype/glory_hype/chart/chartread.py`:

```python
"""ChartRead: structured extraction of everything visible on a HYPE chart.

parse_chart_read is defensive — the agent's vision output may be partial or
sloppy, so we coerce/default rather than crash or store a corrupt row."""

from dataclasses import asdict, dataclass, field

_TRENDS = {"up", "down", "range", "unknown"}


def _num(v):
    """Coerce to float or None."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _num_list(v):
    """Keep only numeric entries of a list; non-list -> []."""
    if not isinstance(v, list):
        return []
    out = []
    for x in v:
        n = _num(x)
        if n is not None:
            out.append(n)
    return out


def _str_list(v):
    if not isinstance(v, list):
        return []
    return [str(x) for x in v]


@dataclass
class ChartRead:
    ts: int
    timeframe: str
    exchange_pair: str
    price_range_low: float | None
    price_range_high: float | None
    current_price: float | None
    swing_high: float | None
    swing_low: float | None
    trend: str
    support_levels: list = field(default_factory=list)
    resistance_levels: list = field(default_factory=list)
    patterns: list = field(default_factory=list)
    signals: list = field(default_factory=list)
    indicators: dict = field(default_factory=dict)
    position: dict | None = None
    orders: list = field(default_factory=list)
    annotations: list = field(default_factory=list)
    visible_text: list = field(default_factory=list)
    notes: str = ""
    image_path: str | None = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def parse_chart_read(data: dict, ts: int, image_path: str | None) -> ChartRead:
    d = data if isinstance(data, dict) else {}
    trend = d.get("trend")
    trend = trend if isinstance(trend, str) and trend in _TRENDS else "unknown"
    timeframe = d.get("timeframe")
    timeframe = timeframe if isinstance(timeframe, str) and timeframe else "unknown"
    pair = d.get("exchange_pair")
    pair = pair if isinstance(pair, str) else ""
    position = d.get("position")
    position = position if isinstance(position, dict) else None
    indicators = d.get("indicators")
    indicators = indicators if isinstance(indicators, dict) else {}
    return ChartRead(
        ts=ts,
        timeframe=timeframe,
        exchange_pair=pair,
        price_range_low=_num(d.get("price_range_low")),
        price_range_high=_num(d.get("price_range_high")),
        current_price=_num(d.get("current_price")),
        swing_high=_num(d.get("swing_high")),
        swing_low=_num(d.get("swing_low")),
        trend=trend,
        support_levels=_num_list(d.get("support_levels")),
        resistance_levels=_num_list(d.get("resistance_levels")),
        patterns=_str_list(d.get("patterns")),
        signals=_str_list(d.get("signals")),
        indicators=indicators,
        position=position,
        orders=_str_list(d.get("orders")),
        annotations=_str_list(d.get("annotations")),
        visible_text=_str_list(d.get("visible_text")),
        notes=str(d.get("notes", "")),
        image_path=image_path,
        raw=d,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chartread.py -v`
Expected: PASS (5 passed)

---

### Task 2: Storage — chart_reads table + Store methods

**Files:**
- Modify: `glory-hype/glory_hype/db.py` (add table to SCHEMA + 3 methods)
- Test: `glory-hype/tests/test_chart_store.py`

Context: same `self._lock`/WAL discipline as the v1/v2 Store methods. `json` is already imported at the top of db.py.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_chart_store.py`:

```python
from glory_hype.db import Store


def _read(ts, tf="1h", trend="up", px=65.0):
    return {"ts": ts, "timeframe": tf, "trend": trend, "current_price": px,
            "support_levels": [64.0], "resistance_levels": [66.0],
            "patterns": ["flag"], "indicators": {"rsi": 70}, "image_path": None,
            "notes": "n"}


def test_insert_and_latest(tmp_path):
    s = Store(str(tmp_path / "c.db"))
    s.insert_chart_read(_read(1000))
    s.insert_chart_read(_read(2000, trend="down", px=64.0))
    latest = s.latest_chart_read()
    assert latest["ts"] == 2000
    assert latest["trend"] == "down"
    assert latest["support_levels"] == [64.0]      # JSON round-trips
    assert latest["indicators"] == {"rsi": 70}


def test_recent_filters_by_time(tmp_path):
    s = Store(str(tmp_path / "c2.db"))
    s.insert_chart_read(_read(100))
    s.insert_chart_read(_read(9000))
    rows = s.recent_chart_reads(since_ts=5000)
    assert [r["ts"] for r in rows] == [9000]


def test_latest_none_when_empty(tmp_path):
    s = Store(str(tmp_path / "c3.db"))
    assert s.latest_chart_read() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chart_store.py -v`
Expected: FAIL — `insert_chart_read` not defined.

- [ ] **Step 3: Add the table to SCHEMA**

In `glory-hype/glory_hype/db.py`, append to the `SCHEMA` string (before its closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS chart_reads (
    ts INTEGER PRIMARY KEY,
    timeframe TEXT,
    trend TEXT,
    current_price REAL,
    image_path TEXT,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chart_ts ON chart_reads(ts);
CREATE INDEX IF NOT EXISTS idx_chart_trend ON chart_reads(trend);
```

- [ ] **Step 4: Add Store methods**

Add to the `Store` class in `db.py`:

```python
    def insert_chart_read(self, read: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO chart_reads
                   (ts, timeframe, trend, current_price, image_path, json)
                   VALUES (?,?,?,?,?,?)""",
                (read["ts"], read.get("timeframe"), read.get("trend"),
                 read.get("current_price"), read.get("image_path"),
                 json.dumps(read)),
            )
            self.conn.commit()

    def recent_chart_reads(self, since_ts: int) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT json FROM chart_reads WHERE ts >= ? ORDER BY ts DESC",
                (since_ts,),
            ).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def latest_chart_read(self):
        with self._lock:
            r = self.conn.execute(
                "SELECT json FROM chart_reads ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return json.loads(r["json"]) if r else None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chart_store.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full suite (no regression)**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser pytest -q`
Expected: all prior tests still pass (schema addition is additive).

---

### Task 3: record_chart_read (image save + persist)

**Files:**
- Create: `glory-hype/glory_hype/chart/record.py`
- Test: `glory-hype/tests/test_chart_record.py`

Context: saves the pasted image bytes under `charts/hype-<ts>.png`, parses the read, stores it. Image-save failure must not block persistence. Takes a `charts_dir` param (defaulting to a `charts/` dir next to the package) so tests can point at tmp_path.

- [ ] **Step 1: Write the failing test**

`glory-hype/tests/test_chart_record.py`:

```python
from pathlib import Path
from glory_hype.db import Store
from glory_hype.chart.record import record_chart_read


def test_record_saves_image_and_row(tmp_path):
    s = Store(str(tmp_path / "r.db"))
    charts = tmp_path / "charts"
    read = record_chart_read(
        s, {"timeframe": "1h", "trend": "up", "current_price": 65.0},
        image_bytes=b"\x89PNG fake", charts_dir=str(charts), ts=1234)
    assert read.timeframe == "1h"
    assert read.image_path is not None
    assert Path(read.image_path).exists()
    assert Path(read.image_path).read_bytes() == b"\x89PNG fake"
    assert s.latest_chart_read()["ts"] == 1234


def test_record_without_image(tmp_path):
    s = Store(str(tmp_path / "r2.db"))
    read = record_chart_read(s, {"trend": "down"}, image_bytes=None,
                             charts_dir=str(tmp_path / "charts"), ts=7)
    assert read.image_path is None
    assert s.latest_chart_read()["trend"] == "down"


def test_record_image_failure_still_persists(tmp_path, monkeypatch):
    s = Store(str(tmp_path / "r3.db"))
    import glory_hype.chart.record as rec

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(rec, "_write_image", boom)
    read = record_chart_read(s, {"trend": "range"}, image_bytes=b"x",
                             charts_dir=str(tmp_path / "charts"), ts=3)
    assert read.image_path is None          # save failed, gracefully None
    assert s.latest_chart_read()["ts"] == 3  # row still persisted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chart_record.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`glory-hype/glory_hype/chart/record.py`:

```python
"""Record a chart read: save the image, parse defensively, persist to the store."""

import time
from pathlib import Path

from glory_hype.chart.chartread import ChartRead, parse_chart_read

_DEFAULT_CHARTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "charts")


def _write_image(path: Path, image_bytes: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)


def record_chart_read(store, data: dict, image_bytes: bytes | None = None,
                      charts_dir: str = _DEFAULT_CHARTS_DIR,
                      ts: int | None = None) -> ChartRead:
    if ts is None:
        ts = int(time.time() * 1000)
    image_path = None
    if image_bytes:
        path = Path(charts_dir) / f"hype-{ts}.png"
        try:
            _write_image(path, image_bytes)
            image_path = str(path)
        except Exception:
            image_path = None  # image is a bonus; the read is what matters
    read = parse_chart_read(data, ts=ts, image_path=image_path)
    store.insert_chart_read(read.to_dict())
    return read
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd glory-hype && uv run --with pytest pytest tests/test_chart_record.py -v`
Expected: PASS (3 passed)

---

### Task 4: Dashboard endpoint + panel + CLI

**Files:**
- Modify: `glory-hype/glory_hype/server.py` (add `/api/chart`)
- Modify: `glory-hype/glory_hype/static/index.html` (Chart panel)
- Modify: `glory-hype/glory_hype/__main__.py` (`chart` subcommand)
- Modify: `glory-hype/.gitignore` (ignore `charts/`)
- Test: `glory-hype/tests/test_chart_server.py`

- [ ] **Step 1: Write the failing server test**

`glory-hype/tests/test_chart_server.py`:

```python
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def seeded(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.insert_chart_read({"ts": 1234, "timeframe": "1h", "trend": "up",
                         "current_price": 65.6, "support_levels": [64.0],
                         "resistance_levels": [66.8], "patterns": ["flag"],
                         "indicators": {"rsi": 68}, "image_path": None,
                         "notes": "extended"})
    return s


def test_chart_endpoint(tmp_path):
    app = create_app(seeded(tmp_path))
    client = TestClient(app)
    r = client.get("/api/chart")
    assert r.status_code == 200
    body = r.json()
    assert body["read"]["trend"] == "up"
    assert body["read"]["support_levels"] == [64.0]


def test_chart_endpoint_empty(tmp_path):
    app = create_app(Store(str(tmp_path / "e.db")))
    client = TestClient(app)
    r = client.get("/api/chart")
    assert r.status_code == 200
    assert r.json()["read"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_chart_server.py -v`
Expected: FAIL — `/api/chart` 404.

- [ ] **Step 3: Add the endpoint**

In `glory-hype/glory_hype/server.py`, add inside `create_app` (after the narrative routes):

```python
    @app.get("/api/chart")
    def chart():
        return {"read": store.latest_chart_read()}
```

- [ ] **Step 4: Run server test to pass**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx pytest tests/test_chart_server.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Add the dashboard Chart panel**

In `glory-hype/glory_hype/static/index.html`, add before `</body>` (after the Narrative panel):

```html
  <h2 style="font-size:14px;margin-top:24px;">Chart Read</h2>
  <div id="chart" class="card">No chart read yet.</div>

<script>
function renderChart(d){
  const r = d.read;
  const el = document.getElementById("chart");
  if (!r){ el.textContent = "No chart read yet."; return; }
  const cls = r.trend==='up'?'pos':(r.trend==='down'?'neg':'');
  el.innerHTML = `<div class="label">${r.timeframe||'?'} · ${new Date(r.ts).toLocaleString()}</div>
    <div class="val ${cls}">${(r.trend||'unknown').toUpperCase()} @ ${r.current_price ?? '—'}</div>
    <div style="font-size:12px;margin-top:6px;">Support: ${(r.support_levels||[]).join(', ')||'—'} ·
      Resistance: ${(r.resistance_levels||[]).join(', ')||'—'}</div>
    <div style="font-size:12px;">Patterns: ${(r.patterns||[]).join(', ')||'—'}</div>
    <div style="font-size:12px;">Indicators: ${Object.entries(r.indicators||{}).map(([k,v])=>k+'='+v).join(', ')||'—'}</div>
    <div style="font-size:12px;color:#8b97a7;margin-top:4px;">${r.notes||''}</div>`;
}
function loadChart(){ fetch("/api/chart").then(r=>r.json()).then(renderChart); }
loadChart();
setInterval(loadChart, 15000);
</script>
```

- [ ] **Step 6: Add the `chart` CLI subcommand**

In `glory-hype/glory_hype/__main__.py`: add `"chart"` to the `choices` list; add an argparse argument for `--file` and `--image`; add imports `from glory_hype.chart.record import record_chart_read` and `import json as _json` (if not already imported). Add the branch:

```python
    elif args.cmd == "chart":
        with open(args.file, encoding="utf-8") as f:
            data = _json.load(f)
        image_bytes = None
        if args.image:
            with open(args.image, "rb") as f:
                image_bytes = f.read()
        read = record_chart_read(store, data, image_bytes=image_bytes)
        print(_json.dumps(read.to_dict(), indent=2))
```

And add the args near the existing `--db`/`--port` definitions:

```python
    p.add_argument("--file", help="path to ChartRead JSON (for `chart`)")
    p.add_argument("--image", help="path to chart screenshot (for `chart`)")
```

- [ ] **Step 7: Ignore the charts directory**

Append to `glory-hype/.gitignore`:

```
# Saved chart screenshots (kept locally for v5 learning, not versioned)
charts/
```

- [ ] **Step 8: Run the full offline suite**

Run: `cd glory-hype && uv run --with pytest --with fastapi --with httpx --with websockets --with feedparser pytest -q`
Expected: ALL green (v1 + v2 + v3).

---

### Task 5: Commit (GATED — only after user approval)

> Do NOT run until the user explicitly says to commit.

- [ ] **Step 1: Stage and commit**

```bash
cd E:/Glory
git add glory-hype/glory_hype/chart glory-hype/glory_hype/db.py \
  glory-hype/glory_hype/server.py glory-hype/glory_hype/static/index.html \
  glory-hype/glory_hype/__main__.py glory-hype/.gitignore \
  glory-hype/tests/test_chartread.py glory-hype/tests/test_chart_store.py \
  glory-hype/tests/test_chart_record.py glory-hype/tests/test_chart_server.py \
  docs/superpowers/specs/2026-05-30-hype-chart-reader-design.md \
  docs/superpowers/plans/2026-05-30-hype-chart-reader.md
git commit -m "feat(hype): v3 chart reader — structured ChartRead from pasted charts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- ChartRead schema (all fields incl. position/orders/visible_text catch-all) → Task 1 ✓
- Defensive parse (valid/partial/garbage/bad-levels) → Task 1 tests ✓
- chart_reads table + Store methods (insert/recent/latest) → Task 2 ✓
- Image persistence to charts/ + graceful failure → Task 3 ✓
- record_chart_read → Task 3 ✓
- /api/chart endpoint + dashboard panel → Task 4 ✓
- `chart` CLI subcommand → Task 4 ✓
- charts/ gitignored → Task 4 step 7 ✓
- Agent-as-vision (no vision-model code) → by design; not a build task ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code; every command has expected output.

**Type consistency:** `ChartRead` fields and `to_dict()` keys match the Store columns (`ts`, `timeframe`, `trend`, `current_price`, `image_path`) and the JSON blob. `parse_chart_read(data, ts, image_path)` signature is consistent across Tasks 1, 3. `record_chart_read(store, data, image_bytes, charts_dir, ts)` signature matches its tests. Store methods (`insert_chart_read`, `recent_chart_reads`, `latest_chart_read`) named identically across Tasks 2, 3, 4. `/api/chart` returns `{"read": ...}` consistent between server impl and tests. `_write_image` is the monkeypatch seam used by the failure test.
