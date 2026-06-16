# glory-hype v10 Design Spec
**Date:** 2026-06-04  
**Scope:** Engine improvements, multi-perp architecture, dashboard redesign  
**Status:** Approved

---

## 1. Engine Improvements

### 1.1 Synthesizer → LM Studio Gemma

**Problem:** `Synthesizer` hardcodes `ProxyClient(model="kimi")` which routes through `localhost:8082` (glory proxy). This proxy is often offline, leaving synthesis unavailable and blocking the decision gate.

**Fix:** Add LM Studio config to `config.py`. `Synthesizer.__init__` builds a `ProxyClient` pointed at LM Studio by default, with the glory proxy as a named fallback.

```python
# config.py additions
LM_STUDIO_URL = "http://169.254.83.107:1234"
LM_STUDIO_MODEL = "90f9618340396838ee7ff5b0ba2da27da62953d3"
```

`Synthesizer(store)` constructs `ProxyClient(base_url=LM_STUDIO_URL, model=LM_STUDIO_MODEL)`. No new client class — `ProxyClient` already speaks OpenAI-compatible `/v1/chat/completions`. The system prompt is unchanged.

**Fallback:** If LM Studio returns a `ProxyError`, write `unavailable()` conclusion as before.

### 1.2 Stale Synthesis Gate: 6h → 12h (configurable)

**Problem:** 6h stale threshold was designed for a cloud LLM that is always up. Gemma on LM Studio goes offline when the machine sleeps or the user closes it.

**Fix:**
- Raise default `NARRATIVE_STALE_MS` from 6h to 12h in `config.py`.
- Read an optional `synthesis_stale_hours` key from the `settings` table at gate evaluation time. If present, override the default. This allows per-session tightening from the dashboard settings panel.

### 1.3 Confidence Calibration: Narrative Score Modifier

**Problem:** `record_call()` only applies a confidence modifier from pattern signal matches. When `matches` is empty (no pattern fires), the modifier is 0 and the LLM judgment confidence passes through raw.

**Fix:** Add a second modifier sourced from the synthesis conclusion:

```
conclusion bias == trade direction AND score >= 65  →  +0.05
conclusion bias == opposite direction               →  -0.10
conclusion unavailable or neutral                  →   0.00
```

Both modifiers (pattern + narrative) are summed, capped at `±PATTERN_CONF_MODIFIER_MAX`. Applied in `engine.py` after the pattern modifier.

### 1.4 Raise MIN_RR: 1.0 → 1.5

The Jun 3 long (R:R 0.374) demonstrated that MIN_RR=1.0 allows thin setups through. The new floor of 1.5 rejects marginal risk/reward while still permitting asymmetric trades (the Jun 4 long at 66 had R:R 4.75).

---

## 2. Multi-Perp Architecture

### 2.1 Asset Config Registry

Replace hardcoded `COIN = "HYPE"` and `DB_PATH = "hype.db"` with a typed `AssetConfig` dataclass and an `ASSETS` registry dict in `config.py`:

```python
@dataclass
class AssetConfig:
    coin: str           # Hyperliquid coin symbol
    db: str             # SQLite DB filename
    large_trade_ntl: float  # USD notional threshold for "large" trades

ASSETS: dict[str, AssetConfig] = {
    "hype": AssetConfig(coin="HYPE", db="hype.db", large_trade_ntl=50_000),
    "near": AssetConfig(coin="NEAR", db="near.db", large_trade_ntl=5_000),
    "icp":  AssetConfig(coin="ICP",  db="icp.db",  large_trade_ntl=5_000),
    "vvv":  AssetConfig(coin="VVV",  db="vvv.db",  large_trade_ntl=5_000),
}
```

Adding a new perp requires one dict entry and the corresponding DB will be created on first run.

### 2.2 Server: Asset-Prefixed Routes

`create_app(store: Store)` becomes `create_app(assets: dict[str, Store])`.

All data routes gain an `/{asset}/` prefix:

```
GET  /api/assets                    → list of assets + latest price/24h change
GET  /api/{asset}/snapshot
GET  /api/{asset}/narrative
POST /api/{asset}/narrative/synthesize
GET  /api/{asset}/chart
POST /api/{asset}/chart/upload
GET  /api/{asset}/chart/pending
GET  /api/{asset}/decision
GET  /api/{asset}/settings
POST /api/{asset}/settings
GET  /api/{asset}/track
GET  /api/{asset}/patterns
GET  /api/{asset}/events
POST /api/{asset}/events/analyze
GET  /api/{asset}/stream             (SSE)
GET  /api/{asset}/health
```

`GET /api/assets` returns:
```json
[
  {"slug": "hype", "coin": "HYPE", "price": 74.5, "change_24h": -6.2},
  {"slug": "near", "coin": "NEAR", "price": 2.31, "change_24h": -17.1},
  ...
]
```

`GET /` still serves the single `index.html`.

**Unknown asset slug** returns HTTP 404 with `{"detail": "unknown asset: xyz"}`.

### 2.3 CLI: Asset Flag

```bash
python -m glory_hype collect --asset hype   # collect for one asset
python -m glory_hype serve                  # unified server, all assets auto-discovered
python -m glory_hype decide --asset hype --file judgment.json
```

`serve` with no `--asset` discovers all assets whose DB files exist on disk.

### 2.4 Backward Compatibility

`hype.db` exists today with 30k+ candles and all current data. No migration. The `hype` slug maps to it directly. All current behavior is preserved — the server just gains additional asset routes alongside the existing (now prefixed) ones.

---

## 3. Dashboard Redesign

### 3.1 Visual Theme

| Token | Value | Use |
|---|---|---|
| Background | `#08080f` | Page background |
| Card | `#0f0f1a` | Panel surfaces |
| Border | `#1e1e35` | Card borders, dividers |
| Purple | `#8b5cf6` | Active states, confidence, interactive |
| Purple dim | `#7c3aed` | Hover, pressed |
| Gold | `#f59e0b` | Prices, key numbers, SHORT signals |
| Green | `#10b981` | Profit, LONG signals, positive change |
| Red | `#ef4444` | Loss, negative change |
| Text primary | `#f1f5f9` | Headings, labels |
| Text secondary | `#94a3b8` | Subtext, timestamps |

Font: Inter (Google Fonts CDN), `font-feature-settings: "tnum"` on all numeric elements for tabular figures.

### 3.2 Top Bar (sticky)

```
[Glory]  [HYPE] [NEAR] [ICP] [VVV]          $74.50  -6.2% ▼
```

- **Glory wordmark**: white, bold, left-aligned
- **Asset pills**: rounded, inactive = `#1e1e35` border; active = `#8b5cf6` background + subtle glow `box-shadow: 0 0 12px #8b5cf640`
- **Live price**: gold, right-aligned; 24h change badge: green/red pill
- Switching pills calls `setAsset(slug)` which updates a global `currentAsset` and re-fetches all panels

### 3.3 Stats Ribbon

One sticky row below the top bar. Five stat cards inline:

`Mark Price` · `24h Change` · `Funding Rate` · `Open Interest` · `24h Volume`

Gold numbers, secondary muted labels. Refreshes every 5s from `/api/{asset}/stream`.

### 3.4 Tabs

`Market | Charts | Trade | Intel` — same four tabs. Active tab: purple underline + primary text. Inactive: secondary text, no underline. No box borders on the tab bar.

### 3.5 Events Intelligence Panel (Intel Tab)

Each upcoming event renders as a card with:

**Header row:**
- Event label (e.g. "Team Vesting Unlock — Jun 6") — primary text, bold
- Days-until badge: purple if >3 days, gold if ≤3 days, red if ≤1 day

**Why it's happening:**
Plain-English description from the event catalog (e.g. "Scheduled TGE vesting — 684M USD team allocation begins unlocking. Insiders gain liquid access to sell."). Text secondary color.

**Trade signal badge:**
- `LONG BEFORE` (green) if `median_pre > 0` and confidence ≥ small-sample threshold
- `SHORT AFTER` (gold/amber) if `median_post < 0`
- `NEUTRAL` (muted) if N < 3 or signals conflict
- N= sample size shown inline: `(N=5)`

**Expected move pills:**
- Pre-event: `+8.8%` green pill
- Post-event: `-7.8%` red pill

**Watch also:**
Comma-separated list of correlated assets with brief reason (e.g. `NEAR, ICP — Hayes portfolio; both dropped -15%+ on Jun 4 alongside HYPE`). Gold text, italic.

**Backend changes for enriched events:**

Add to `EventCatalog` entries:
- `description: str` — why it's happening
- `correlated_assets: list[str]` — other perps to watch
- `signals: list[str]` — one or both of `"long_pre"`, `"short_post"` — derived at `analyze_events()` time: append `"long_pre"` if `median_pre > 0`, append `"short_post"` if `median_post < 0`. Empty list = `"neutral"`. Both can be present (e.g. Jun 6 unlock has both).

`/api/{asset}/events` response includes `description`, `correlated_assets`, and `direction` on each event.

---

## 4. Files Changed

| File | Change |
|---|---|
| `glory_hype/config.py` | Add `LM_STUDIO_URL`, `LM_STUDIO_MODEL`, `AssetConfig`, `ASSETS`; raise `NARRATIVE_STALE_MS` to 12h; raise `MIN_RR` to 1.5 |
| `glory_hype/narrative/synthesize.py` | Default to LM Studio client |
| `glory_hype/decision/engine.py` | Add narrative score modifier; read configurable stale threshold |
| `glory_hype/decision/gates.py` | Read `synthesis_stale_hours` from settings |
| `glory_hype/events/catalog.py` | Add `description`, `correlated_assets`, `direction` fields; update HYPE events |
| `glory_hype/events/upcoming.py` | Return enriched fields; derive `direction` from composite |
| `glory_hype/server.py` | `create_app(assets)`, asset-prefixed routes, `/api/assets` |
| `glory_hype/__main__.py` | `--asset` flag for collect/decide; serve auto-discovers all assets |
| `glory_hype/static/index.html` | Full redesign — Glory palette, sticky top bar, asset selector, stats ribbon, enriched Events panel |

---

## 5. Out of Scope (v11+)

- Cross-asset correlation engine (HYPE/NEAR/ICP/VVV co-movement signals)
- Automated synthesis scheduling (cron-style synthesis every N hours)
- Chart upload per-asset routing
- Pattern library cross-asset training
