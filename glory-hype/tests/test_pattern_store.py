from glory_hype.db import Store


def test_pattern_stats_upsert_and_read(tmp_path):
    s = Store(str(tmp_path / "p.db"))
    s.upsert_pattern_stat({"pattern_name": "COIL_EXPANSION", "source": "hand",
                           "n_train": 20, "n_test": 8, "win_rate_train": 0.75,
                           "win_lo_test": 0.61, "win_hi_test": 0.92,
                           "avg_move_pct": 5.2, "avg_move_hrs": 6, "direction": "up",
                           "stable": 1})
    rows = s.stable_pattern_stats(min_conf=0.60)
    assert len(rows) == 1 and rows[0]["pattern_name"] == "COIL_EXPANSION"
    # below threshold or unstable excluded
    s.upsert_pattern_stat({"pattern_name": "WEAK", "source": "disc", "n_train": 12,
                           "n_test": 5, "win_rate_train": 0.6, "win_lo_test": 0.40,
                           "win_hi_test": 0.7, "avg_move_pct": 3.0, "avg_move_hrs": 6,
                           "direction": "up", "stable": 1})
    assert len(s.stable_pattern_stats(min_conf=0.60)) == 1   # WEAK lo 0.40 < 0.60


def test_pattern_event_and_regime(tmp_path):
    s = Store(str(tmp_path / "p2.db"))
    s.insert_regime({"ts": 100, "timeframe": "1h", "label": "coiling", "features_json": "{}"})
    s.insert_pattern_event({"ts": 100, "pattern_name": "COIL_EXPANSION", "source": "hand",
                            "direction": "up", "features_json": "{}",
                            "fwd_4h": 4.2, "fwd_12h": 5.0, "fwd_24h": 3.1})
    assert s.conn.execute("SELECT COUNT(*) FROM regimes").fetchone()[0] == 1
    assert s.conn.execute("SELECT COUNT(*) FROM pattern_events").fetchone()[0] == 1


def test_pattern_stat_extended_columns(tmp_path):
    from glory_hype.db import Store
    s = Store(str(tmp_path / "ext.db"))
    s.upsert_pattern_stat({"pattern_name": "P", "source": "hand", "n_train": 30,
                           "n_test": 12, "win_rate_train": 0.7, "win_lo_test": 0.62,
                           "win_hi_test": 0.9, "avg_move_pct": 5.0, "avg_move_hrs": 12,
                           "direction": "up", "stable": 1, "threshold": 3.0,
                           "horizon": 12, "p_value": 0.002, "bh_significant": 1,
                           "holdout_lo": 0.58, "n_holdout": 8})
    row = s.all_pattern_stats()[0]
    assert row["threshold"] == 3.0 and row["horizon"] == 12
    assert row["bh_significant"] == 1 and row["holdout_lo"] == 0.58
