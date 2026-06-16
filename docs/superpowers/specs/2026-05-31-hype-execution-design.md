---
title: Glory HYPE — Autonomous Execution (v6)
date: 2026-05-31
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v6 of 8 (execution; v7 learning, v8 learning-driven execution follow)
builds_on: 2026-05-30-hype-decision-engine-design.md
---

# Glory HYPE — Autonomous Execution (v6)

## Purpose

Turn a v4 TradeCall into a real order on Hyperliquid, fired with one click from the
dashboard, using a **Hyperliquid agent (API) wallet** so Glory can trade but can never
withdraw funds. Every order and fill is logged — the data v7 learns from. This is the
first layer of the mastery loop: **execution → learning → learning-driven execution**.

## Decisions locked (from brainstorming)

- **Execution path: native Hyperliquid agent API** (not browser harness). Robust, fast,
  confirmable fills, every order type. Requires a VPN running for the geo-blocked
  *trading* endpoint — the public *data* endpoints (v1) already work without one.
- **Agent wallet, not the main key.** A Hyperliquid agent wallet can place orders but
  **cannot withdraw** (protocol-enforced). The user's real funds-controlling key (in
  axiom/Turnkey) is never touched.
- **Signing via the official `hyperliquid-python-sdk`** — no hand-rolled EIP-712.
- **Chart reading stays agent-in-session** (drop → Glory reads → finalize), unchanged.
- **One-click confirm** autonomy: Glory stages the order, the user clicks Fire.
- **Vault unlocked once at server startup** (CLI passphrase prompt); the agent key lives
  in memory for the session, never on disk in plaintext.

## One-time setup (documented, user does once)

1. With VPN on, the user goes to `app.hyperliquid.xyz/API`, connects the wallet axiom
   funds, and **generates + approves an API (agent) wallet**. Hyperliquid shows the agent
   private key once.
2. User runs `python -m glory_hype import-key` → pastes the **agent** private key and the
   **main account address** → Glory seals the key into a `glory-core` vault
   (`agent.vault`) with a passphrase. (Safe to hand Glory this key — it cannot withdraw.)
3. Thereafter `serve.bat` prompts for the passphrase once at startup to unlock it.

If the user's axiom-funded account cannot approve an agent (fully walled off), fallback
is the community axiom account-API SDK — documented as plan B, not built in v6.

## Architecture / files

```
glory-hype/glory_hype/
  exchange/
    __init__.py
    keystore.py     # wrap glory-core vault: import_agent_key, unlock -> (agent_key, main_addr)
    hl_client.py    # hyperliquid-python-sdk wrapper: market/limit/reduce-only/trigger orders
    execute.py      # execute_call(store, key, addr): re-gate + place bracket + log fills
  safety.py         # pure: pre-execution rails (freshness, drift, daily-loss, max-size)
  db.py             # MODIFY: orders + fills tables + methods
  server.py         # MODIFY: POST /api/execute (uses in-memory unlocked key), /api/orders
  static/index.html # MODIFY: "Fire" button on the Decision panel + fill display
  __main__.py       # MODIFY: import-key CLI; serve unlocks vault at startup
  config.py         # MODIFY: DAILY_LOSS_CAP_USD, MAX_POSITION_USD, DRIFT_PCT, FRESH_MS
```

New dependency: `hyperliquid-python-sdk` (brings `eth_account`). Added to requirements +
pyproject.

### keystore.py
- `import_agent_key(agent_privkey_hex, main_address, passphrase, path)` → `vault.seal(...)`.
- `unlock(passphrase, path) -> (agent_privkey_bytes, main_address)` → `vault.open_vault(...)`.
  The stored blob is JSON `{"key": "0x...", "address": "0x..."}` serialized to bytes.

### hl_client.py
Thin wrapper over `hyperliquid.exchange.Exchange` constructed with an `eth_account`
`LocalAccount` (the agent key) + `account_address=main_address` + mainnet base URL.
Methods, all returning the SDK's fill/status response:
- `market_open(is_buy, sz)` / `market_close()` (reduce-only)
- `limit_order(is_buy, px, sz, tif="Gtc", reduce_only=False)`
- `trigger_order(is_buy, trigger_px, sz, is_tp, reduce_only=True)` — for TP/SL brackets
- `open_positions()` / `user_fills()` — read back actual state
On network failure (VPN down / geo-block), raises `ExchangeUnreachable` with a clear
"exchange unreachable — is the VPN running?" message.

### safety.py (pure)
`check_rails(call, live_mark, now_ms, todays_realized_pnl, cfg) -> list[str]`:
- call older than `FRESH_MS` (5 min) → reason
- `abs(live_mark - call.entry)/call.entry > DRIFT_PCT` (1%) → reason
- `call.position_notional > MAX_POSITION_USD` → reason
- `todays_realized_pnl <= -DAILY_LOSS_CAP_USD` → reason ("daily loss cap hit")
Empty list = clear to fire. Fully unit-testable.

### execute.py
`execute_call(store, hl_client, call) -> dict`:
1. Re-fetch live ctx; `check_rails(...)`. Any reason → return `{"status":"blocked","reasons":[...]}`, log nothing.
2. Place the **entry**: market if within drift of mark, else limit at entry.
3. Place **TP** (reduce-only trigger/limit at call.tp) and **SL** (reduce-only trigger at call.sl) — the bracket.
4. Record each order + returned fill in `orders`/`fills`; link to `call.generated_at`.
5. Return `{"status":"filled","orders":[...],"fills":[...]}`.

### Storage
- `orders`: `id` (oid/cloid), `call_at`, `ts`, `type` (market/limit/trigger), `side`,
  `px`, `sz`, `reduce_only`, `status`, `raw_json`.
- `fills`: `tid`, `order_id`, `ts`, `px`, `sz`, `fee`, `closed_pnl`, `raw_json`.
- Methods: `insert_order`, `insert_fill`, `recent_orders`, `todays_realized_pnl`
  (sum of `closed_pnl` for fills since local midnight — feeds the daily-loss rail).

### Server + dashboard
- Vault is unlocked at startup; the unlocked `hl_client` lives on the app state.
- `POST /api/execute` → `execute_call(...)`; returns filled/blocked. 503 if exchange
  unreachable (VPN). Returns 409 if no fresh actionable call.
- `GET /api/orders` → recent orders + fills.
- Dashboard **Fire button** on the Decision panel (only when decision is long/short and
  rails would pass); on click → `/api/execute` → shows fills or the block reasons. After
  firing, shows the live position + the bracket.

## Safety rails (hard-coded; configurable thresholds)

Server-side, enforced before any order signs:
- **Freshness** < 5 min, **price drift** < 1% from entry.
- **Max position** ($ cap) and **daily loss cap** ($ cap; refuses to fire once breached).
- Agent wallet **cannot withdraw** (protocol) — the ultimate backstop.
- VPN/connection failure → no order placed, explicit error.

## Error handling

- Exchange unreachable (VPN down/geo) → `ExchangeUnreachable` → 503, nothing placed.
- Partial bracket (entry fills, TP/SL placement fails) → record what placed, return
  `status="partial"` with the gap flagged so the user can fix the missing leg manually.
- SDK error / rejected order → captured, logged, returned with the venue's message;
  no silent failure.
- Vault locked / not imported → `/api/execute` returns a clear "agent key not unlocked"
  rather than crashing.
- Re-gate at execution time means a call that went stale between display and click is
  blocked, not fired.

## Verification / success criteria

- `check_rails` independently blocks on each rail (unit-tested: stale, drift, over-size,
  loss-cap).
- `keystore` seals + unlocks an agent key round-trip (temp vault, test passphrase).
- `hl_client` order methods build the correct SDK payloads (tested against a mocked SDK;
  no real orders in tests).
- `execute_call` blocks when rails fail and places+logs a bracket when they pass (mocked
  client + seeded store).
- A **testnet** end-to-end (Hyperliquid testnet) places a real test order and reads the
  fill back — the only "live" check, opt-in, never against mainnet funds in tests.
- Dashboard Fire button executes and shows the fill (manual check, testnet first).

## Testing

- **Offline-unit:** `safety.check_rails` (all rails), `keystore` round-trip, `hl_client`
  payload construction (mocked SDK), `execute_call` (blocked + filled + partial via mocked
  client), order/fill store + `todays_realized_pnl`, `/api/execute` + `/api/orders` via
  `TestClient` with a mocked client on app state.
- **Opt-in live (`live` marker, testnet only):** import a testnet agent key, place + cancel
  a tiny test order, read the fill. Never runs by default; never touches mainnet.

## Out of scope for v6

- v7 (learning from these fills) and v8 (learning-driven calls).
- Trailing stops, auto re-entry, scaling in/out, multi-leg strategies.
- Fully unattended firing — v6 is one-click confirm; the user is present.

## The mastery loop (context)

v6 = the hands (execute + log). v7 = realized-P&L + per-condition edge from these fills,
fed into v4. v8 = v4 calls weighted by learned edge, then the loop compounds. Mastery —
understanding the market deeply enough to extract durable edge — never manipulation.
