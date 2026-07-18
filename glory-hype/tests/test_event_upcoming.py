import time
from glory_hype.db import Store
from glory_hype.events.upcoming import analyze_events, upcoming_events

HR = 3600_000


def _candle(ts, c):
    return {"interval": "1h", "open_ts": ts, "close_ts": ts + HR - 1,
            "o": c, "h": c * 1.001, "l": c * 0.999, "c": c, "v": 1.0, "n": 1}


def _seed_unlock_history(s, base, n):
    # n past unlocks, each: dip then recover, spaced 30d apart
    for k in range(n):
        ev = base + k * 30 * 86400_000
        s.insert_event({"date_ms": ev, "type": "unlock", "label": f"unlock {k}",
                        "magnitude_pct": 2.0, "magnitude_usd": 1e8, "source_url": "",
                        "notes": ""})
        for h in range(-48, 49):
            price = 100.0 + (h * -0.05 if h < 0 else h * 0.08)  # dip in, rise out
            s.insert_candle(_candle(ev + h * HR, price))


def test_analyze_builds_composite(tmp_path):
    s = Store(str(tmp_path / "u.db"))
    base = 1_700_000_000_000
    _seed_unlock_history(s, base, 4)
    res = analyze_events(s)
    assert res["types"]["unlock"]["n"] == 4
    st = s.event_study("unlock")
    assert st["n"] == 4 and st["median_pre"] < 0     # dipped into the event


def test_upcoming_attaches_composite_and_flag(tmp_path):
    s = Store(str(tmp_path / "u2.db"))
    base = 1_700_000_000_000
    _seed_unlock_history(s, base, 3)
    analyze_events(s)
    now = base + 100 * 86400_000
    s.insert_event({"date_ms": now + 2 * 86400_000, "type": "unlock",
                    "label": "future unlock", "magnitude_pct": 2.5,
                    "magnitude_usd": 6.8e8, "source_url": "", "notes": ""})
    up = upcoming_events(s, now_ms=now, horizon_days=14)
    assert len(up) == 1
    e = up[0]
    assert e["days_until"] == 2
    assert e["proximity"] is True                    # <= 3 days
    assert e["composite"]["n"] == 3                   # unlock history attached
