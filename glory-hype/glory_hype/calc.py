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
