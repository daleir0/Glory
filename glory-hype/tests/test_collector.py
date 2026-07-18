from glory_hype.db import Store
from glory_hype.collector import Collector


class FakeRest:
    def candle_snapshot(self, coin, interval, start_ms, end_ms):
        return [{"interval": interval, "open_ts": 0, "close_ts": 59, "o": 1.0,
                 "h": 2.0, "l": 0.5, "c": 1.5, "v": 9.0, "n": 4}]

    def asset_ctx(self, coin):
        return {"funding": 0.0001, "open_interest": 10.0, "mark_px": 62.0,
                "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                "prev_day_px": 56.0, "day_ntl_vlm": 1.0}


def make(tmp_path):
    store = Store(str(tmp_path / "c.db"))
    return Collector(store=store, rest=FakeRest()), store


def test_backfill_writes_candles(tmp_path):
    col, store = make(tmp_path)
    col.backfill_interval("1m")
    assert store.latest_candle("1m")["c"] == 1.5


def test_poll_ctx_writes_latest(tmp_path):
    col, store = make(tmp_path)
    col.poll_once(now_ms=1234)
    assert store.latest_ctx()["mark_px"] == 62.0


def test_apply_ws_candle_message(tmp_path):
    col, store = make(tmp_path)
    col.apply_ws_message({"channel": "candle", "data": {
        "t": 1000, "T": 1059, "s": "HYPE", "i": "1m", "o": "1", "c": "2",
        "h": "3", "l": "0.5", "v": "9", "n": 4}})
    assert store.latest_candle("1m")["c"] == 2.0


def test_apply_ws_large_trade_message(tmp_path):
    col, store = make(tmp_path)
    col.apply_ws_message({"channel": "trades", "data": [
        {"coin": "HYPE", "side": "B", "px": "62.0", "sz": "1000", "time": 5,
         "hash": "0x", "tid": 7, "users": []}]})
    assert store.recent_large_trades()[0]["tid"] == 7
