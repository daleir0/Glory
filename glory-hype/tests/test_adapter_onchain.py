from glory_hype.db import Store
from glory_hype.narrative.adapters.onchain import OnchainAdapter


def _ctx(mark, oi, funding):
    return {"funding": funding, "open_interest": oi, "mark_px": mark,
            "oracle_px": mark, "mid_px": mark, "premium": 0.0,
            "prev_day_px": mark, "day_ntl_vlm": 1.0}


def test_onchain_flags_oi_surge(tmp_path):
    s = Store(str(tmp_path / "o.db"))
    s.insert_ctx(_ctx(60, 1_000_000, 0.0001), ts=1_000)
    s.insert_ctx(_ctx(61, 1_120_000, 0.0001), ts=100_000)  # +12% OI
    items = OnchainAdapter(s, oi_surge_pct=10.0).fetch()
    assert any("open interest" in i.title.lower() for i in items)
    assert all(i.source == "onchain" and i.reliability_weight == 1.0 for i in items)


def test_onchain_flags_funding_flip(tmp_path):
    s = Store(str(tmp_path / "o2.db"))
    s.insert_ctx(_ctx(60, 1_000_000, 0.0002), ts=1_000)     # positive
    s.insert_ctx(_ctx(60, 1_000_000, -0.0002), ts=100_000)  # flipped negative
    items = OnchainAdapter(s).fetch()
    assert any("funding" in i.title.lower() for i in items)


def test_onchain_flags_large_trade_cluster(tmp_path):
    import time
    base_ts = int(time.time() * 1000)
    s = Store(str(tmp_path / "o3.db"))
    s.insert_ctx(_ctx(60, 1_000_000, 0.0001), ts=base_ts - 100_000)
    s.insert_ctx(_ctx(60, 1_000_000, 0.0001), ts=base_ts - 1_000)
    for i in range(6):
        s.insert_trade({"ts": base_ts - 5_000 + i, "px": 60.0, "sz": 1000.0, "side": "B",
                        "tid": i, "ntl": 60000.0, "is_large": True})
    items = OnchainAdapter(s, large_cluster_min=5, window_ms=60_000).fetch()
    assert any("large" in i.title.lower() for i in items)


def test_onchain_quiet_market_no_events(tmp_path):
    s = Store(str(tmp_path / "o4.db"))
    s.insert_ctx(_ctx(60, 1_000_000, 0.0001), ts=1_000)
    s.insert_ctx(_ctx(60, 1_005_000, 0.0001), ts=100_000)  # +0.5% OI, no flip
    items = OnchainAdapter(s, oi_surge_pct=10.0).fetch()
    assert items == []
