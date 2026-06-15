"""Pure hard gates for the decision engine. Any returned reason => no_trade.

R:R and liquidation gates are applied later in the engine (they need sizing);
these gates cover input freshness/validity/availability."""


def evaluate_gates(ctx, conclusion, chart_read, now_ms, cfg, store=None) -> list:
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
        else:
            stale_ms = cfg.NARRATIVE_STALE_MS
            if store:
                hours = store.get_setting("synthesis_stale_hours", None)
                if hours:
                    stale_ms = float(hours) * 3_600_000
            stale_h = int(stale_ms / 3_600_000)
            if now_ms - conclusion.get("generated_at", 0) > stale_ms:
                reasons.append(f"Narrative conclusion is stale (>{stale_h}h old).")

    if not chart_read:
        reasons.append("No chart read on record to anchor entry/TP/SL.")
    elif chart_read.get("flags"):
        reasons.append("Chart read is flagged (data integrity): "
                       + "; ".join(chart_read["flags"]))

    return reasons
