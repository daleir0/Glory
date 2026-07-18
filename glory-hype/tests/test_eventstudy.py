from glory_hype.events.eventstudy import study_event, composite

HR = 3600_000


def _candle(ts, c):
    return {"interval": "1h", "open_ts": ts, "close_ts": ts + HR - 1,
            "o": c, "h": c * 1.001, "l": c * 0.999, "c": c, "v": 1.0, "n": 1}


def test_study_event_pre_post():
    event_ms = 1_000_000_000_000
    # window -2h..+2h: price 100 (pre) dips to 96 at event, recovers to 102 after
    candles = [_candle(event_ms - 2 * HR, 100.0), _candle(event_ms - HR, 98.0),
               _candle(event_ms, 96.0), _candle(event_ms + HR, 99.0),
               _candle(event_ms + 2 * HR, 102.0)]
    st = study_event({"date_ms": event_ms, "type": "unlock"}, candles, [], window_days=1)
    assert round(st["pre_pct"], 1) == -4.0      # 100 -> 96 into the event
    assert round(st["post_pct"], 2) == 6.25     # 96 -> 102 after (rel to event close)
    assert st["trough_pct"] < 0
    assert st["peak_pct"] > 0
    assert st["n_candles"] == 5


def test_study_event_no_data():
    st = study_event({"date_ms": 5, "type": "unlock"}, [], [], window_days=7)
    assert st["n_candles"] == 0
    assert st["pre_pct"] is None


def test_composite_median_and_label():
    studies = [{"pre_pct": -3.0, "post_pct": 4.0, "trough_pct": -6.0, "peak_pct": 5.0},
               {"pre_pct": -5.0, "post_pct": 2.0, "trough_pct": -8.0, "peak_pct": 3.0},
               {"pre_pct": -1.0, "post_pct": 6.0, "trough_pct": -4.0, "peak_pct": 7.0}]
    c = composite(studies, "unlock")
    assert c["n"] == 3
    assert c["median_pre"] == -3.0       # median of -3,-5,-1
    assert "N=3" in c["confidence_label"]


def test_composite_small_n_label():
    c = composite([{"pre_pct": -3.0, "post_pct": 4.0, "trough_pct": -6.0, "peak_pct": 5.0}],
                  "unlock")
    assert c["n"] == 1
    assert "insufficient" in c["confidence_label"].lower()


def test_composite_empty():
    c = composite([], "unlock")
    assert c["n"] == 0
    assert c["median_pre"] is None
