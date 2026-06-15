"""Compute per-type event-study composites and surface upcoming catalysts."""

import json
import time

from glory_hype import config
from glory_hype.events.eventstudy import composite, study_event


def analyze_events(store) -> dict:
    """Study every PAST event against our candles, build per-type composites, persist."""
    candles = store.recent_candles("1h", 100000)
    now = int(time.time() * 1000)
    by_type = {}
    for e in store.all_events():
        if e["date_ms"] >= now:
            continue   # only past events are studiable
        st = study_event(e, candles, [], config.EVENT_WINDOW_DAYS)
        if st["n_candles"] > 0:
            by_type.setdefault(e["type"], []).append(st)
    out = {}
    for type_, studies in by_type.items():
        c = composite(studies, type_)
        store.upsert_event_study({
            "type": type_, "n": c["n"], "median_pre": c["median_pre"],
            "median_post": c["median_post"], "median_trough": c["median_trough"],
            "median_peak": c["median_peak"], "spread_json": json.dumps(c["spread"]),
            "confidence_label": c["confidence_label"], "computed_at": now})
        out[type_] = c
    return {"types": out}


def upcoming_events(store, now_ms: int, horizon_days: int) -> list:
    rows = store.upcoming_events_raw(now_ms, horizon_days)
    out = []
    for e in rows:
        days = (e["date_ms"] - now_ms) / 86400_000
        st = store.event_study(e["type"])
        signals = []
        if st:
            if (st.get("median_pre") or 0) > 0:
                signals.append("long_pre")
            if (st.get("median_post") or 0) < 0:
                signals.append("short_post")
        corr_raw = e.get("correlated_assets")
        try:
            correlated = json.loads(corr_raw) if corr_raw else []
        except (TypeError, ValueError):
            correlated = []
        out.append({
            "label": e["label"], "type": e["type"], "date_ms": e["date_ms"],
            "days_until": int(days),
            "proximity": days <= config.EVENT_PROXIMITY_DAYS,
            "magnitude_pct": e["magnitude_pct"], "magnitude_usd": e["magnitude_usd"],
            "description": e.get("description") or "",
            "correlated_assets": correlated,
            "signals": signals,
            "composite": st if st else {"n": 0, "confidence_label": "no comparable history"},
        })
    return out
