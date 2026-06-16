from glory_hype.chart.flags import divergence_flags


def test_no_flag_within_tolerance():
    assert divergence_flags(65.5, 65.8, tol_pct=5.0) == []


def test_flag_on_large_divergence():
    flags = divergence_flags(87.85, 65.82, tol_pct=5.0)
    assert len(flags) == 1
    assert "diverg" in flags[0].lower()
    assert "33" in flags[0]              # ~33.5%
    assert "65.82" in flags[0]           # cites the live mark


def test_no_flag_when_inputs_missing():
    assert divergence_flags(None, 65.8) == []
    assert divergence_flags(87.0, None) == []
    assert divergence_flags(87.0, 0) == []   # avoid div-by-zero


def test_boundary_just_over_tolerance():
    # 70 vs 65 = 7.69% > 5%
    flags = divergence_flags(70.0, 65.0, tol_pct=5.0)
    assert len(flags) == 1


def _seed_ctx(store, mark):
    store.insert_ctx({"funding": 0.0, "open_interest": 1.0, "mark_px": mark,
                      "oracle_px": mark, "mid_px": mark, "premium": 0.0,
                      "prev_day_px": mark, "day_ntl_vlm": 1.0}, ts=1)


def test_finalize_flags_divergent_read(tmp_path):
    from glory_hype.db import Store
    from glory_hype.chart.record import finalize_chart_read
    s = Store(str(tmp_path / "f.db"))
    _seed_ctx(s, 65.82)
    s.insert_pending_chart_read(ts=100, image_path=None)
    # a misread at 87.85 against a 65.82 mark must be flagged
    read = finalize_chart_read(s, 100, {"current_price": 87.85, "trend": "range"})
    assert read.flags and "diverg" in read.flags[0].lower()
    assert s.latest_chart_read()["flags"]      # persisted


def test_finalize_no_flag_when_aligned(tmp_path):
    from glory_hype.db import Store
    from glory_hype.chart.record import finalize_chart_read
    s = Store(str(tmp_path / "f2.db"))
    _seed_ctx(s, 65.82)
    s.insert_pending_chart_read(ts=200, image_path=None)
    # the corrected 67.6 read is ~2.8% from mark -> no flag
    read = finalize_chart_read(s, 200, {"current_price": 67.642, "trend": "range"})
    assert read.flags == []
