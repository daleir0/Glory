from glory_hype.db import Store


def test_settings_get_set_default(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    assert s.get_setting("account_balance", "0") == "0"   # default
    s.set_setting("account_balance", "1000")
    assert s.get_setting("account_balance", "0") == "1000"
    s.set_setting("account_balance", "1500")              # overwrite
    assert s.get_setting("account_balance", "0") == "1500"
    assert s.get_settings()["account_balance"] == "1500"


def test_trade_calls_store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.insert_trade_call({"generated_at": 100, "decision": "long",
                         "entry": 67.4, "rationale": "x", "gates_failed": []})
    s.insert_trade_call({"generated_at": 200, "decision": "no_trade",
                         "gates_failed": ["stale"]})
    latest = s.latest_trade_call()
    assert latest["generated_at"] == 200
    assert latest["decision"] == "no_trade"
    assert latest["gates_failed"] == ["stale"]            # JSON round-trips
    assert len(s.recent_trade_calls(since_ts=0)) == 2
