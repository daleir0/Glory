"""Decision engine: gather inputs -> hard gates -> size (calculator) -> persist."""

import time

from glory_hype import config
from glory_hype import config as _cfg
from glory_hype.calc import compute_trade
from glory_hype.decision.gates import evaluate_gates
from glory_hype.decision.tradecall import TradeCall, no_trade, parse_judgment
from glory_hype.events.upcoming import upcoming_events
from glory_hype.patterns.detector import current_signal
from glory_hype.track.resolver import track_summary


def record_call(store, judgment: dict) -> TradeCall:
    now = int(time.time() * 1000)
    ctx = store.latest_ctx()
    conclusion = store.latest_conclusion()
    chart_read = store.latest_chart_read()

    gates = evaluate_gates(ctx, conclusion, chart_read, now, config, store=store)
    inputs = {"ctx_ts": (ctx or {}).get("ts"),
              "conclusion_at": (conclusion or {}).get("generated_at"),
              "chart_read_ts": (chart_read or {}).get("ts"),
              "track_record": track_summary(store)}
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

    signal = current_signal(store)
    inputs["pattern_signal"] = signal
    up = upcoming_events(store, now, config.EVENT_ALERT_DAYS)
    nearest = up[0] if up else None
    caution = bool(nearest and nearest["type"] in ("unlock", "etf")
                   and (nearest["date_ms"] - now) <= config.EVENT_CAUTION_HRS * 3600_000)
    inputs["event_context"] = {"nearest": nearest, "caution": caution}
    # confidence modifier: agreeing stable pattern lifts, conflicting one trims
    if j["decision"] in ("long", "short"):
        want = "up" if j["decision"] == "long" else "down"
        mod = 0.0
        for m in signal["matches"]:
            edge = (m["confidence"] - 0.5) / 0.5 * _cfg.PATTERN_CONF_MODIFIER_MAX
            mod += edge if m["direction"] == want else -edge
        mod = max(-_cfg.PATTERN_CONF_MODIFIER_MAX, min(_cfg.PATTERN_CONF_MODIFIER_MAX, mod))
        j["confidence"] = max(0.0, min(1.0, j["confidence"] + mod))

    # narrative modifier: synthesis conclusion alignment with trade direction
    if conclusion and j["decision"] in ("long", "short"):
        bias = (conclusion.get("bias") or "").lower()
        score = float(conclusion.get("score") or 0)
        trade_bullish = j["decision"] == "long"
        if (bias == "bullish" and trade_bullish) or (bias == "bearish" and not trade_bullish):
            if score >= 65:
                j["confidence"] = max(0.0, min(1.0, j["confidence"] + 0.05))
        elif (bias == "bullish" and not trade_bullish) or (bias == "bearish" and trade_bullish):
            j["confidence"] = max(0.0, min(1.0, j["confidence"] - 0.10))

    # sizing inputs from settings. Total equity = untraded balance + open position value.
    untraded = float(store.get_setting("account_balance", "0") or 0)
    position_value = float(store.get_setting("position_value", "0") or 0)
    account = untraded + position_value
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
