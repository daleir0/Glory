from glory_hype.db import Store


def test_insert_and_query_events(tmp_path):
    s = Store(str(tmp_path / "e.db"))
    s.insert_event({"date_ms": 1000, "type": "unlock", "label": "Jan unlock",
                    "magnitude_pct": 0.5, "magnitude_usd": 1e6, "source_url": "u",
                    "notes": "n"})
    s.insert_event({"date_ms": 9_000_000_000_000, "type": "unlock",
                    "label": "future unlock", "magnitude_pct": 2.5,
                    "magnitude_usd": 6.8e8, "source_url": "u2", "notes": ""})
    assert len(s.all_events()) == 2
    assert len(s.events_of_type("unlock")) == 2
    up = s.upcoming_events_raw(now_ms=2000, horizon_days=365 * 100)
    assert len(up) == 1 and up[0]["label"] == "future unlock"


def test_event_study_roundtrip(tmp_path):
    s = Store(str(tmp_path / "e2.db"))
    s.upsert_event_study({"type": "unlock", "n": 5, "median_pre": -3.0,
                          "median_post": 4.0, "median_trough": -6.0,
                          "median_peak": 5.0, "spread_json": "{}",
                          "confidence_label": "small-sample composite (N=5)",
                          "computed_at": 1})
    st = s.event_study("unlock")
    assert st["n"] == 5 and st["median_pre"] == -3.0
    assert s.all_event_studies()[0]["type"] == "unlock"
