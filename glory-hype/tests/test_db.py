from glory_hype.db import Store


def make_store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_insert_and_get_latest_candle(tmp_path):
    s = make_store(tmp_path)
    c = {"interval": "1m", "open_ts": 1000, "close_ts": 1059, "o": 1.0, "h": 2.0,
         "l": 0.5, "c": 1.5, "v": 10.0, "n": 3}
    s.insert_candle(c)
    assert s.latest_candle("1m")["c"] == 1.5


def test_candle_upsert_on_same_open_ts(tmp_path):
    s = make_store(tmp_path)
    base = {"interval": "1m", "open_ts": 1000, "close_ts": 1059, "o": 1.0, "h": 2.0,
            "l": 0.5, "c": 1.5, "v": 10.0, "n": 3}
    s.insert_candle(base)
    s.insert_candle({**base, "c": 1.9, "v": 12.0, "n": 5})  # same open_ts, updated
    rows = s.candle_open_timestamps("1m")
    assert rows == [1000]                       # not duplicated
    assert s.latest_candle("1m")["c"] == 1.9  # overwritten


def test_insert_ctx_and_trade_and_book(tmp_path):
    s = make_store(tmp_path)
    s.insert_ctx({"funding": 0.0001, "open_interest": 100.0, "mark_px": 62.1,
                  "oracle_px": 62.2, "mid_px": 62.15, "premium": -0.0001,
                  "prev_day_px": 56.9, "day_ntl_vlm": 1000.0}, ts=2000)
    assert s.latest_ctx()["mark_px"] == 62.1

    s.insert_trade({"ts": 3000, "px": 62.0, "sz": 1000.0, "side": "B",
                    "tid": 99, "ntl": 62000.0, "is_large": True})
    assert s.recent_large_trades(limit=10)[0]["tid"] == 99

    s.insert_book(ts=4000, bids=[{"px": 1, "sz": 2, "n": 1}],
                  asks=[{"px": 2, "sz": 3, "n": 1}])
    assert s.latest_book()["ts"] == 4000


def test_recent_large_trades_filter(tmp_path):
    s = make_store(tmp_path)
    s.insert_trade({"ts": 1000, "px": 10.0, "sz": 500.0, "side": "B",
                    "tid": 1, "ntl": 5000.0, "is_large": True})
    s.insert_trade({"ts": 2000, "px": 10.0, "sz": 1.0, "side": "A",
                    "tid": 2, "ntl": 10.0, "is_large": False})
    results = s.recent_large_trades(limit=10)
    assert len(results) == 1
    assert results[0]["tid"] == 1
