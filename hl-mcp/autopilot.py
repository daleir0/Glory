"""
Glory HYPE Confluence Engine v5 — trend-aware spike trading + full setup coverage.

WHAT v4 MISSED:
  - Spike detected → blocked entry → did nothing. That's wrong.
  - After a spike UP into a DOWNTREND, the correct trade is to FADE it SHORT immediately.
  - After a spike DOWN into an UPTREND, fade it LONG immediately.
  - The dip-entry (wait for retrace) is only correct when the spike is WITH the trend.
  - The engine also never tracked the 200m macro trend, so it had no context for which
    way to fade.

v5 SPIKE DECISION MATRIX (trend-aware):
  Spike UP   + MACRO DOWNTREND  -> FADE SHORT immediately (spike into resistance)
  Spike UP   + MACRO UPTREND    -> wait for dip, enter LONG at 40% retrace
  Spike DOWN + MACRO UPTREND    -> FADE LONG immediately (spike into support)
  Spike DOWN + MACRO DOWNTREND  -> wait for bounce, enter SHORT at 40% retrace
  Spike any  + MACRO NEUTRAL    -> wait for retrace (safer, no trend conviction)

Fade entries only require: trend confirmed + 1+ confluence signal agrees + chop cleared.
Dip/top retrace entries require: MIN_AGREE-1 confluent + 0 opposing.
Standard entries: MIN_AGREE=3 agreeing + 0 opposing (unchanged).

New signal: macro_trend — 200m price drift classifies the sustained directional bias.

Signals (10 total):
  1. flow         — aggregate large-trade buy/sell pressure ratio
  2. funding      — crowding read from funding rate + premium
  3. oi_delta     — OI direction vs price direction matrix (persisted)
  4. regime       — glory-hype pattern regime; macro-filtered (bounce in downtrend = neutral)
  5. narrative    — glory-hype narrative synthesis (weighted by its own confidence)
  6. drift_30m    — 30m candle drift; macro-filtered (pullback in downtrend = neutral)
  7. whale        — individual trades >$75K: real money positioning
  8. structure    — 60m macro range position: near support vs. resistance
  9. macro_trend  — 200m drift: sustained directional bias
 10. momentum_5m  — 5-candle real-time direction (what drift_30m is too slow to see)
"""
import os
import time
import math
import json
import requests
from dotenv import load_dotenv
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BASE_URL = "https://api.hyperliquid.xyz"
GLORY_API = "http://localhost:5179/api"
COIN = "HYPE"
SLUG = "hype"

# --- Config ---
TARGET_EQUITY = 100.0
FLOOR_EQUITY = 20.0
BASE_LEVERAGE = 10
NOTIONAL = 130.0
MIN_AGREE = 3            # need >=3 signals agreeing, 0 opposing
MIN_NOTIONAL = 10.5
SLIPPAGE_PCT = 0.4
# Hunt Day TP/SL (quick scalp — default)
ATR_TP_MULT = 2.0
ATR_SL_MULT = 1.3
# Dip/Fade-entry TP/SL — wider because post-spike volatility is elevated
ATR_TP_DIP = 2.5
ATR_SL_DIP = 1.8
# Profit Day TP/SL — hold for bigger structural move
ATR_TP_PROFIT = 4.5
ATR_SL_PROFIT = 1.5
# Profit Day classification score threshold
PROFIT_DAY_SCORE = 50
MIN_RANGE_FOR_ENTRY = 0.35   # chop filter: range% < this = too noisy for a stop
SPIKE_ATR_MULT = 2.5         # candle range > this * ATR = spike, block entry
SPIKE_RETRACE_PCT = 0.40     # wait for 40% retrace before dip entry
SPIKE_MAX_AGE_MIN = 30       # discard spike state after 30 min
WHALE_MIN_NTL = 75_000       # single trade >= $75K = whale print

STATE_DIR = os.path.dirname(__file__)
OI_STATE   = os.path.join(STATE_DIR, "oi_state.json")
SPIKE_STATE = os.path.join(STATE_DIR, "spike_state.json")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ex():
    w = Account.from_key(os.environ["HL_PRIVATE_KEY"])
    return Exchange(w, BASE_URL), w.address


def round_px(px):
    if px <= 0:
        return px
    digits = 4 - int(math.floor(math.log10(abs(px))))
    return round(px, max(0, digits))


def fetch_glory():
    snap     = requests.get(f"{GLORY_API}/{SLUG}/snapshot", timeout=8).json()
    patterns = requests.get(f"{GLORY_API}/{SLUG}/patterns", timeout=8).json()
    narrative = requests.get(f"{GLORY_API}/{SLUG}/narrative", timeout=8).json()
    return snap, patterns, narrative


def candle_stats(snap, minutes=30):
    candles = snap.get("candles_1m", [])[-minutes:]
    if len(candles) < 5:
        return None
    highs  = [float(c["h"]) for c in candles]
    lows   = [float(c["l"]) for c in candles]
    closes = [float(c["c"]) for c in candles]
    rng_high, rng_low = max(highs), min(lows)
    last   = closes[-1]
    rng_pct = (rng_high - rng_low) / last * 100
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = highs[i], lows[i], closes[i-1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs) / len(trs) if trs else (rng_high - rng_low)
    drift_pct = (closes[-1] - closes[0]) / closes[0] * 100
    return {"range_pct": rng_pct, "atr": atr, "atr_pct": atr/last*100,
            "drift_pct": drift_pct, "last": last, "high": rng_high, "low": rng_low}


def macro_trend_200m(snap):
    """Classify the 200m sustained trend from all available 1m candles."""
    candles = snap.get("candles_1m", [])
    if len(candles) < 10:
        return "neutral"
    first = float(candles[0]["c"])
    last  = float(candles[-1]["c"])
    drift = (last - first) / first * 100
    if drift > 1.5:
        return "uptrend"
    elif drift < -1.5:
        return "downtrend"
    return "neutral"


def take_screenshot():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            br = p.chromium.launch(headless=True)
            pg = br.new_page(viewport={"width": 1280, "height": 720})
            pg.goto("http://localhost:5179", timeout=8000)
            pg.wait_for_timeout(1000)
            pg.screenshot(path=os.path.join(STATE_DIR, "chart_snap.png"))
            br.close()
    except Exception:
        pass  # non-critical, never block trading on a screenshot failure


# ─── State I/O ────────────────────────────────────────────────────────────────

def load_oi_state():
    try:
        with open(OI_STATE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_oi_state(oi, price):
    with open(OI_STATE, "w") as f:
        json.dump({"ts": time.time(), "oi": oi, "px": price}, f)


def load_spike_state():
    try:
        with open(SPIKE_STATE) as f:
            s = json.load(f)
        if time.time() - s.get("ts", 0) > SPIKE_MAX_AGE_MIN * 60:
            os.remove(SPIKE_STATE)
            return None
        return s
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_spike_state(direction, spike_high, spike_low, entry_target):
    with open(SPIKE_STATE, "w") as f:
        json.dump({"ts": time.time(), "direction": direction,
                   "spike_high": spike_high, "spike_low": spike_low,
                   "entry_target": entry_target}, f)


def clear_spike_state():
    try:
        os.remove(SPIKE_STATE)
    except FileNotFoundError:
        pass


# ─── Spike / chart structure analysis ────────────────────────────────────────

def analyze_spike(snap, cs):
    """
    Gate entry timing with trend-aware spike decision matrix. Returns:
      None                      — no spike context, normal confluence entry allowed
      ('fade', dir, reason)     — spike AGAINST macro trend: fade immediately (e.g. spike UP in downtrend → SHORT)
      ('block', reason)         — spike WITH/neutral trend: recorded for dip/bounce entry, no immediate entry
      ('wait', dir, target)     — spike recorded in prior cycle, price hasn't retraced yet
      ('dip_entry', dir)        — retrace level reached: this IS the entry signal
    """
    if not cs:
        return None

    candles = snap.get("candles_1m", [])
    if len(candles) < 2:
        return None

    atr = cs["atr"]
    last = candles[-1]
    last_range = float(last["h"]) - float(last["l"])

    # Is the most recent candle a spike?
    if last_range > atr * SPIKE_ATR_MULT:
        is_up = float(last["c"]) > float(last["o"])
        spike_dir = "up" if is_up else "down"
        sh, sl = float(last["h"]), float(last["l"])
        trend = macro_trend_200m(snap)

        # Spike AGAINST the macro trend → FADE it immediately, no dip wait
        if (spike_dir == "up" and trend == "downtrend") or (spike_dir == "down" and trend == "uptrend"):
            fade_dir = "short" if spike_dir == "up" else "long"
            reason = (f"spike {spike_dir} {last_range/atr:.1f}x ATR into {trend} "
                      f"→ FADE {fade_dir.upper()} immediately")
            return ("fade", fade_dir, reason)

        # Spike WITH trend or neutral → wait for dip/bounce (buy the dip / sell the bounce)
        trade_dir = "long" if spike_dir == "up" else "short"
        target = sl + last_range * SPIKE_RETRACE_PCT if spike_dir == "up" else sh - last_range * SPIKE_RETRACE_PCT
        save_spike_state(spike_dir, sh, sl, target)
        return ("block", f"spike {spike_dir} {last_range/atr:.1f}x ATR ({trend}), "
                         f"{trade_dir} dip entry @ {target:.3f}")

    # Check for pending spike (from a prior cycle)
    spike = load_spike_state()
    if spike:
        current_px = float(candles[-1]["c"])
        if spike["direction"] == "up":
            if current_px <= spike["entry_target"]:
                clear_spike_state()
                return ("dip_entry", "long")
            return ("wait", "long", spike["entry_target"])
        else:
            if current_px >= spike["entry_target"]:
                clear_spike_state()
                return ("dip_entry", "short")
            return ("wait", "short", spike["entry_target"])

    return None


# ─── Signal votes ─────────────────────────────────────────────────────────────

def vote(name, direction, weight, why):
    return {"signal": name, "dir": direction, "weight": weight, "why": why}


def build_confluence(snap, patterns, narrative, cs, oi_prev):
    votes = []
    ctx = snap["ctx"]
    candles = snap.get("candles_1m", [])
    mt = macro_trend_200m(snap)  # computed once, used to filter regime + drift

    # 1. Aggregate large-trade flow
    lt = snap.get("large_trades", [])[:20]
    buy  = sum(t["ntl"] for t in lt if t["side"] == "B")
    sell = sum(t["ntl"] for t in lt if t["side"] == "A")
    tot  = buy + sell
    flow = (buy - sell) / tot if tot else 0.0
    if flow > 0.20:
        votes.append(vote("flow", "long",  min(abs(flow), 1.0), f"buy-flow dominant ({flow:+.2f})"))
    elif flow < -0.20:
        votes.append(vote("flow", "short", min(abs(flow), 1.0), f"sell-flow dominant ({flow:+.2f})"))
    else:
        votes.append(vote("flow", "neutral", 0, f"flow balanced ({flow:+.2f})"))

    # 2. Funding + premium (crowding)
    funding_bp  = ctx["funding"] * 1e4
    premium_pct = ctx["premium"] * 100
    if funding_bp > 1.0 and premium_pct > 0.05:
        votes.append(vote("funding", "short", 0.6, f"longs crowded ({funding_bp:.2f}bp / {premium_pct:+.3f}%)"))
    elif funding_bp < -1.0 and premium_pct < -0.05:
        votes.append(vote("funding", "long",  0.6, f"shorts crowded ({funding_bp:.2f}bp / {premium_pct:+.3f}%)"))
    else:
        votes.append(vote("funding", "neutral", 0, f"benign ({funding_bp:.3f}bp / {premium_pct:+.4f}%)"))

    # 3. OI delta vs price delta
    oi_now = ctx["open_interest"]
    px_now = ctx["mark_px"]
    if oi_prev:
        oi_d = (oi_now - oi_prev["oi"]) / oi_prev["oi"] * 100
        px_d = (px_now - oi_prev["px"]) / oi_prev["px"] * 100
        if abs(oi_d) < 0.15 or abs(px_d) < 0.15:
            votes.append(vote("oi_delta", "neutral", 0, f"OI {oi_d:+.2f}% / px {px_d:+.2f}% too small"))
        elif px_d > 0 and oi_d > 0:
            votes.append(vote("oi_delta", "long",  min(abs(oi_d)/2, 1.0), f"px {px_d:+.2f}% + OI {oi_d:+.2f}% -> fresh longs"))
        elif px_d < 0 and oi_d > 0:
            votes.append(vote("oi_delta", "short", min(abs(oi_d)/2, 1.0), f"px {px_d:+.2f}% + OI {oi_d:+.2f}% -> fresh shorts"))
        elif px_d > 0 and oi_d < 0:
            votes.append(vote("oi_delta", "neutral", 0, f"px up + OI down -> short cover, not fresh demand"))
        else:
            votes.append(vote("oi_delta", "neutral", 0, f"px down + OI down -> long liq, not fresh supply"))
    else:
        votes.append(vote("oi_delta", "neutral", 0, "establishing OI baseline"))
    save_oi_state(oi_now, px_now)

    # 4. Pattern regime (macro-filtered: short-term bounce/dip against 200m trend = noise)
    regime = patterns.get("regime", "unknown")
    if (regime == "trending_up" and mt == "downtrend") or (regime == "trending_down" and mt == "uptrend"):
        votes.append(vote("regime", "neutral", 0, f"regime={regime} filtered (macro={mt})"))
    elif regime == "trending_up":
        votes.append(vote("regime", "long",  0.5, "regime=trending_up"))
    elif regime == "trending_down":
        votes.append(vote("regime", "short", 0.5, "regime=trending_down"))
    else:
        votes.append(vote("regime", "neutral", 0, f"regime={regime}"))

    # 5. Narrative
    concl = narrative.get("conclusion", {})
    bias  = concl.get("bias", "neutral")
    nconf = concl.get("score", 0)
    if bias == "bullish" and nconf > 20:
        votes.append(vote("narrative", "long",  min(nconf/100, 1.0), f"bullish (score={nconf})"))
    elif bias == "bearish" and nconf < -20:
        votes.append(vote("narrative", "short", min(abs(nconf)/100, 1.0), f"bearish (score={nconf})"))
    else:
        votes.append(vote("narrative", "neutral", 0, f"{bias} (score={nconf}) no edge"))

    # 6. Short-horizon drift (macro-filtered: drift opposing trend = relief bounce, not reversal)
    if cs:
        d = cs["drift_pct"]
        if (mt == "downtrend" and d > 0) or (mt == "uptrend" and d < 0):
            votes.append(vote("drift_30m", "neutral", 0,
                              f"30m drift {d:+.2f}% filtered (pullback in {mt})"))
        elif d > 0.25:
            votes.append(vote("drift_30m", "long",  min(abs(d)/2, 1.0), f"30m drift {d:+.2f}%"))
        elif d < -0.25:
            votes.append(vote("drift_30m", "short", min(abs(d)/2, 1.0), f"30m drift {d:+.2f}%"))
        else:
            votes.append(vote("drift_30m", "neutral", 0, f"30m drift flat ({d:+.2f}%)"))

    # 7. Whale prints (individual trades >= $75K)
    whale_buys  = [t for t in lt if t["side"] == "B" and t["ntl"] >= WHALE_MIN_NTL]
    whale_sells = [t for t in lt if t["side"] == "A" and t["ntl"] >= WHALE_MIN_NTL]
    buy_ntl  = sum(t["ntl"] for t in whale_buys)
    sell_ntl = sum(t["ntl"] for t in whale_sells)
    if buy_ntl > sell_ntl * 1.5 and buy_ntl > 0:
        biggest = max(t["ntl"] for t in whale_buys)
        votes.append(vote("whale", "long",  min(buy_ntl/300_000, 1.0),
                          f"whale BUY ${buy_ntl/1000:.0f}K n={len(whale_buys)} (max ${biggest/1000:.0f}K)"))
    elif sell_ntl > buy_ntl * 1.5 and sell_ntl > 0:
        biggest = max(t["ntl"] for t in whale_sells)
        votes.append(vote("whale", "short", min(sell_ntl/300_000, 1.0),
                          f"whale SELL ${sell_ntl/1000:.0f}K n={len(whale_sells)} (max ${biggest/1000:.0f}K)"))
    else:
        votes.append(vote("whale", "neutral", 0,
                          f"no whale conviction (B:${buy_ntl/1000:.0f}K S:${sell_ntl/1000:.0f}K)"))

    # 8. Macro structure: 60m range position
    last_60 = candles[-60:] if len(candles) >= 60 else candles
    if last_60:
        macro_h = max(float(c["h"]) for c in last_60)
        macro_l = min(float(c["l"]) for c in last_60)
        macro_r = macro_h - macro_l
        current = float(candles[-1]["c"]) if candles else px_now
        pos = (current - macro_l) / macro_r if macro_r > 0 else 0.5
        if pos < 0.30:
            votes.append(vote("structure", "long",  (0.30 - pos)/0.30,
                              f"near 60m support {pos:.0%} of range [{macro_l:.2f}-{macro_h:.2f}]"))
        elif pos > 0.70:
            votes.append(vote("structure", "short", (pos - 0.70)/0.30,
                              f"near 60m resistance {pos:.0%} of range [{macro_l:.2f}-{macro_h:.2f}]"))
        else:
            votes.append(vote("structure", "neutral", 0,
                              f"mid-range {pos:.0%} [{macro_l:.2f}-{macro_h:.2f}]"))

    # 9. 200m macro trend (mt already computed above)
    if mt == "uptrend":
        first_c = float(candles[0]["c"]) if candles else px_now
        drift_200 = (px_now - first_c) / first_c * 100
        votes.append(vote("macro_trend", "long",  0.7, f"200m uptrend ({drift_200:+.2f}%)"))
    elif mt == "downtrend":
        first_c = float(candles[0]["c"]) if candles else px_now
        drift_200 = (px_now - first_c) / first_c * 100
        votes.append(vote("macro_trend", "short", 0.7, f"200m downtrend ({drift_200:+.2f}%)"))
    else:
        votes.append(vote("macro_trend", "neutral", 0, "200m macro neutral (<1.5% drift)"))

    # 10. 5-minute momentum — real-time direction drift_30m is too slow to catch
    if len(candles) >= 6:
        d5 = (float(candles[-1]["c"]) - float(candles[-6]["c"])) / float(candles[-6]["c"]) * 100
        if d5 > 0.10:
            votes.append(vote("momentum_5m", "long",  min(abs(d5) * 3, 1.0), f"5m momentum {d5:+.3f}%"))
        elif d5 < -0.10:
            votes.append(vote("momentum_5m", "short", min(abs(d5) * 3, 1.0), f"5m momentum {d5:+.3f}%"))
        else:
            votes.append(vote("momentum_5m", "neutral", 0, f"5m flat ({d5:+.3f}%)"))

    return votes


def score_votes(votes):
    long_w  = sum(v["weight"] for v in votes if v["dir"] == "long")
    short_w = sum(v["weight"] for v in votes if v["dir"] == "short")
    long_n  = sum(1 for v in votes if v["dir"] == "long")
    short_n = sum(1 for v in votes if v["dir"] == "short")
    return long_w, short_w, long_n, short_n


def calc_leverage(agree_n, whale_agrees):
    if agree_n >= 5 and whale_agrees:
        return 20
    elif agree_n >= 4:
        return 15
    return 10


def classify_day(snap, votes, cs):
    """
    Score the day's profit potential to decide Hunt vs Profit mode.
    Returns (day_type, score, reason)
      day_type: 'hunt' | 'profit'
      score: 0-100
    """
    ctx    = snap["ctx"]
    candles = snap.get("candles_1m", [])
    lt     = snap.get("large_trades", [])[:30]

    score   = 0
    reasons = []

    # 1. Macro trend strength (200m drift)
    if candles:
        first_c  = float(candles[0]["c"])
        last_c   = float(candles[-1]["c"])
        drift_abs = abs((last_c - first_c) / first_c * 100)
        if drift_abs > 4.0:
            score += 35
            reasons.append(f"macro {drift_abs:.1f}% drift")
        elif drift_abs > 2.5:
            score += 22
            reasons.append(f"macro {drift_abs:.1f}% drift")
        elif drift_abs > 1.5:
            score += 12

    # 2. Net whale conviction
    whale_buy  = sum(t["ntl"] for t in lt if t["side"] == "B" and t["ntl"] >= WHALE_MIN_NTL)
    whale_sell = sum(t["ntl"] for t in lt if t["side"] == "A" and t["ntl"] >= WHALE_MIN_NTL)
    net = abs(whale_buy - whale_sell)
    if net > 2_000_000:
        score += 30
        reasons.append(f"mega-whale ${net/1e6:.1f}M net")
    elif net > 500_000:
        score += 20
        reasons.append(f"whale ${net/1000:.0f}K net")
    elif net > 150_000:
        score += 10

    # 3. Funding extreme
    funding_bp = ctx["funding"] * 1e4
    if abs(funding_bp) > 3.0:
        score += 15
        reasons.append(f"funding {funding_bp:+.1f}bp")
    elif abs(funding_bp) > 1.5:
        score += 8

    # 4. Structure at range extreme (price near 60m high/low)
    if cs and candles:
        last_60 = candles[-60:] if len(candles) >= 60 else candles
        h60 = max(float(c["h"]) for c in last_60)
        l60 = min(float(c["l"]) for c in last_60)
        if h60 > l60:
            pos = (cs["last"] - l60) / (h60 - l60)
            if pos < 0.20 or pos > 0.80:
                score += 15
                reasons.append(f"structure extreme {pos:.0%}")
            elif pos < 0.30 or pos > 0.70:
                score += 8

    day_type = "profit" if score >= PROFIT_DAY_SCORE else "hunt"
    return day_type, score, (", ".join(reasons) if reasons else "normal conditions")


def project_tp_target(snap, direction, entry_px, cs):
    """
    Project TP to the next structural key level for Profit Day entries.
    Uses 200m high/low with range extension, snapped to nearest $2.50.
    """
    candles = snap.get("candles_1m", [])
    atr = cs["atr"] if cs else entry_px * 0.003

    if candles:
        h200 = max(float(c["h"]) for c in candles)
        l200 = min(float(c["l"]) for c in candles)
        range_200 = max(h200 - l200, atr * 3)
    else:
        h200 = entry_px * 1.02
        l200 = entry_px * 0.98
        range_200 = atr * 3

    if direction == "long":
        raw     = max(h200 + range_200 * 0.15, entry_px + atr * ATR_TP_PROFIT)
        snapped = math.ceil(raw / 2.5) * 2.5
        return round_px(max(snapped, entry_px + atr * 3.5))
    else:
        raw     = min(l200 - range_200 * 0.15, entry_px - atr * ATR_TP_PROFIT)
        snapped = math.floor(raw / 2.5) * 2.5
        return round_px(min(snapped, entry_px - atr * 3.5))


# ─── Position management ──────────────────────────────────────────────────────

def manage_open(ex, snap, pos, orders):
    coin    = pos["coin"]
    szi     = float(pos["szi"])
    is_long = szi > 0
    entry   = float(pos["entryPx"])
    upnl    = float(pos["unrealizedPnl"])

    cs = candle_stats(snap) if coin == COIN else None
    atr = cs["atr"] if cs else entry * 0.005
    current_px = cs["last"] if cs else (entry + upnl / abs(szi) if szi != 0 else entry)

    tp_orders = [o for o in orders if o["coin"] == coin and o.get("reduceOnly")
                 and o.get("tpsl") == "tp"]
    sl_orders = [o for o in orders if o["coin"] == coin and o.get("reduceOnly")
                 and o.get("tpsl") == "sl"]

    print(f"\nPosition: {coin} {'LONG' if is_long else 'SHORT'} {abs(szi):.3f} @ ${entry:.4g}  "
          f"px ${current_px:.4g}  uPnL ${upnl:+.2f}  tp={len(tp_orders)} sl={len(sl_orders)}")

    if tp_orders and sl_orders:
        sl_px_cur = float(sl_orders[0].get("triggerPx") or sl_orders[0].get("limitPx") or 0)
        tp_px_cur = float(tp_orders[0].get("triggerPx") or tp_orders[0].get("limitPx") or 0)

        if sl_px_cur and tp_px_cur and abs(tp_px_cur - entry) > 0:
            tp_dist  = abs(tp_px_cur - entry)
            progress = ((current_px - entry) / tp_dist if is_long
                        else (entry - current_px) / tp_dist)

            # Trail to breakeven once 50%+ of the way to TP
            be_sl = round_px(entry + 0.12 * atr if is_long else entry - 0.12 * atr)
            at_be = ((is_long and sl_px_cur >= entry - 0.001) or
                     (not is_long and sl_px_cur <= entry + 0.001))

            if progress >= 0.50 and not at_be:
                for o in sl_orders:
                    try:
                        ex.cancel(coin, o["oid"])
                    except Exception:
                        pass
                close_buy = not is_long
                new_sl = ex.order(coin, close_buy, abs(szi), be_sl,
                                  {"trigger": {"triggerPx": be_sl, "isMarket": True, "tpsl": "sl"}},
                                  reduce_only=True)
                print(f"  -> TRAIL SL → breakeven {be_sl:.4g} "
                      f"({progress:.0%} to TP) → {new_sl['status']}")
                return

        print(f"  -> HOLD (TP@{tp_px_cur:.4g}  SL@{sl_px_cur:.4g})")
        return

    # Missing TP/SL: place protection
    if is_long:
        tp_px = round_px(entry + atr * ATR_TP_MULT)
        sl_px = round_px(entry - atr * ATR_SL_MULT)
    else:
        tp_px = round_px(entry - atr * ATR_TP_MULT)
        sl_px = round_px(entry + atr * ATR_SL_MULT)
    close_buy = not is_long
    tp = ex.order(coin, close_buy, abs(szi), tp_px,
                  {"trigger": {"triggerPx": tp_px, "isMarket": True, "tpsl": "tp"}}, reduce_only=True)
    sl = ex.order(coin, close_buy, abs(szi), sl_px,
                  {"trigger": {"triggerPx": sl_px, "isMarket": True, "tpsl": "sl"}}, reduce_only=True)
    print(f"  -> PROTECT: TP@{tp_px} ({tp['status']})  SL@{sl_px} ({sl['status']})")


# ─── Main cycle ───────────────────────────────────────────────────────────────

def run_cycle():
    ex, addr = _ex()
    info     = Info(BASE_URL, skip_ws=True)
    now_ms   = time.time() * 1000

    print(f"\n{'='*72}")
    print(f"GLORY HYPE CONFLUENCE ENGINE v5 - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*72}")

    state     = info.user_state(addr)
    positions = [p["position"] for p in state.get("assetPositions", [])]
    orders    = info.open_orders(addr)
    spot      = requests.post(f"{BASE_URL}/info",
                              json={"type": "spotClearinghouseState", "user": addr}).json()
    usdc  = float(next((b["total"] for b in spot["balances"] if b["coin"] == "USDC"), 0))
    upnl  = sum(float(p["unrealizedPnl"]) for p in positions)
    equity = usdc + upnl
    print(f"Equity ~${equity:.2f} (spot ${usdc:.2f} + uPnL ${upnl:+.2f})  target ${TARGET_EQUITY:.0f}")

    snap, patterns, narrative = fetch_glory()
    take_screenshot()

    # Cancel stale non-reduce-only orders
    for o in orders:
        if not o.get("reduceOnly"):
            age_min = (now_ms - o["timestamp"]) / 6e4
            if age_min > 15:
                r = ex.cancel(o["coin"], o["oid"])
                print(f"CANCEL stale {o['coin']} oid={o['oid']} ({age_min:.0f}m) -> {r['status']}")

    if positions:
        for p in positions:
            manage_open(ex, snap, p, orders)
        print(f"{'='*72}\n")
        return

    if equity < FLOOR_EQUITY:
        print(f"\nHALT: equity ${equity:.2f} < floor ${FLOOR_EQUITY:.0f}")
        return
    if equity >= TARGET_EQUITY:
        print(f"\nTARGET REACHED: ${equity:.2f}. Standing down.")
        return

    # --- Flat: build confluence read ---
    oi_prev = load_oi_state()
    cs      = candle_stats(snap)
    mid     = float(info.all_mids()[COIN])

    print(f"\nMid: ${mid:.3f}")
    if cs:
        print(f"30m structure: range={cs['range_pct']:.2f}%  ATR%={cs['atr_pct']:.2f}%  "
              f"drift={cs['drift_pct']:+.2f}%  [{cs['low']:.2f} - {cs['high']:.2f}]")

    # --- Spike gate: trend-aware, three outcomes: fade / block / dip_entry ---
    spike_status = analyze_spike(snap, cs)
    if spike_status:
        tag, *args = spike_status
        if tag == "block":
            print(f"\nSPIKE BLOCK: {args[0]}")
            print(f"  -> Spike WITH/neutral trend — recording for dip/bounce entry")
            print(f"{'='*72}\n")
            return
        elif tag == "fade":
            fade_dir, reason = args
            print(f"\nSPIKE FADE: {reason}")
            print(f"  -> Spike AGAINST macro trend — checking confluence for immediate entry")
        elif tag == "wait":
            _wait_dir, target = args
            print(f"\nSPIKE WAIT: post-spike {_wait_dir} setup, waiting for {target:.3f} "
                  f"(current {mid:.3f})")
        elif tag == "dip_entry":
            direction = args[0]
            print(f"\nSPIKE DIP/TOP REACHED: entering {direction.upper()} at retrace level "
                  f"(wider ATR*{ATR_SL_DIP} SL for post-spike volatility)")

    votes = build_confluence(snap, patterns, narrative, cs, oi_prev)
    print("\nSignal votes:")
    for v in votes:
        print(f"  [{v['dir']:<7}] w={v['weight']:.2f}  {v['signal']:<10} {v['why']}")

    long_w, short_w, long_n, short_n = score_votes(votes)
    print(f"\nLONG  votes={long_n} weight={long_w:.2f}")
    print(f"SHORT votes={short_n} weight={short_w:.2f}")

    day_type, day_score, day_reason = classify_day(snap, votes, cs)
    print(f"Day:   {day_type.upper():5s}  score={day_score}/100  ({day_reason})")

    # Chop filter
    if not cs or cs["range_pct"] < MIN_RANGE_FOR_ENTRY:
        print(f"\nNO ENTRY: chop filter (range {cs['range_pct'] if cs else 0:.2f}% < {MIN_RANGE_FOR_ENTRY}%)")
        print(f"{'='*72}\n")
        return

    # --- Determine direction ---
    direction = None
    is_dip_entry = False
    is_fade_entry = False

    if spike_status and spike_status[0] == "fade":
        # Fade: spike against macro trend — relaxed gate: MIN_AGREE-1 agreeing, 0 opposing
        forced_dir = spike_status[1]
        agree_n  = long_n  if forced_dir == "long" else short_n
        oppose_n = short_n if forced_dir == "long" else long_n
        if agree_n >= MIN_AGREE - 1 and oppose_n == 0:
            direction = forced_dir
            is_fade_entry = True
        else:
            print(f"\nFADE SIGNAL (spike vs trend) but confluence not met "
                  f"({agree_n} agree, {oppose_n} oppose) — skipping")
    elif spike_status and spike_status[0] == "dip_entry":
        # Dip/bounce: retrace reached — relaxed gate: MIN_AGREE-1 agreeing, 0 opposing
        forced_dir = spike_status[1]
        agree_n  = long_n  if forced_dir == "long" else short_n
        oppose_n = short_n if forced_dir == "long" else long_n
        if agree_n >= MIN_AGREE - 1 and oppose_n == 0:
            direction = forced_dir
            is_dip_entry = True
        else:
            print(f"\nDIP ENTRY SIGNAL (spike retrace) but confluence not met "
                  f"({agree_n} agree, {oppose_n} oppose) — waiting")
    else:
        # Standard: full gate
        if long_n >= MIN_AGREE and short_n == 0:
            direction = "long"
        elif short_n >= MIN_AGREE and long_n == 0:
            direction = "short"

    if not direction:
        print(f"\nNO ENTRY: confluence not met "
              f"(need >={MIN_AGREE} agreeing, 0 opposing)")
        print(f"{'='*72}\n")
        return

    # --- Fire entry ---
    is_long  = (direction == "long")
    agree_n  = long_n if is_long else short_n
    whale_v  = next((v for v in votes if v["signal"] == "whale"), None)
    whale_agrees = whale_v and whale_v["dir"] == direction
    leverage = calc_leverage(agree_n, whale_agrees)

    sz_dec = next(a["szDecimals"] for a in info.meta()["universe"] if a["name"] == COIN)
    sz     = round(NOTIONAL / mid, sz_dec)
    if sz * mid < MIN_NOTIONAL:
        sz = round(MIN_NOTIONAL / mid, sz_dec)

    try:
        ex.update_leverage(leverage, COIN, True)
    except Exception:
        pass

    entry_px = round_px(mid * (1 + SLIPPAGE_PCT/100) if is_long else mid * (1 - SLIPPAGE_PCT/100))
    r  = ex.order(COIN, is_long, sz, entry_px, {"limit": {"tif": "Ioc"}})
    st = r["response"]["data"]["statuses"][0] if r["status"] == "ok" else r

    # TP/SL sizing: Profit Day holds for the bigger structural move
    is_profit_day = (day_type == "profit")
    if is_profit_day:
        sl_mult    = ATR_SL_PROFIT
        entry_type = ("DIP-PROFIT" if is_dip_entry else
                      "FADE-PROFIT" if is_fade_entry else "CONFLUENCE-PROFIT")
    else:
        sl_mult    = ATR_SL_DIP if (is_dip_entry or is_fade_entry) else ATR_SL_MULT
        tp_mult    = ATR_TP_DIP if (is_dip_entry or is_fade_entry) else ATR_TP_MULT
        entry_type = "DIP-ENTRY" if is_dip_entry else ("FADE-ENTRY" if is_fade_entry else "CONFLUENCE")

    print(f"\n>>> ENTER {direction.upper()} {sz} {COIN} @ ~${entry_px}  "
          f"({entry_type}: {agree_n} signals, {'whale' if whale_agrees else 'no whale'}, {leverage}x lev)")

    if "filled" not in st:
        print(f"    NOT FILLED: {json.dumps(st)}")
    else:
        fill = float(st["filled"]["avgPx"])
        atr  = cs["atr"] if cs else fill * 0.005

        if is_profit_day:
            tp_px = project_tp_target(snap, direction, fill, cs)
        elif is_long:
            tp_px = round_px(fill + atr * tp_mult)
        else:
            tp_px = round_px(fill - atr * tp_mult)

        sl_px = round_px(fill - atr * sl_mult if is_long else fill + atr * sl_mult)

        close_buy = not is_long
        tp = ex.order(COIN, close_buy, sz, tp_px,
                      {"trigger": {"triggerPx": tp_px, "isMarket": True, "tpsl": "tp"}}, reduce_only=True)
        sl = ex.order(COIN, close_buy, sz, sl_px,
                      {"trigger": {"triggerPx": sl_px, "isMarket": True, "tpsl": "sl"}}, reduce_only=True)
        tp_tag = f"ATR×{ATR_TP_PROFIT}" if is_profit_day else f"ATR×{tp_mult}"
        print(f"    Filled @ ${fill:.4g}")
        print(f"    TP @ {tp_px} ({abs(tp_px-fill)/fill*100:.2f}%, {tp_tag}) -> {tp['status']}")
        print(f"    SL @ {sl_px} ({abs(sl_px-fill)/fill*100:.2f}%, ATR×{sl_mult}) -> {sl['status']}")

    print(f"{'='*72}\n")


if __name__ == "__main__":
    run_cycle()
