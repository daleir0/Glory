from glory_hype.hl_ws import subscribe_messages, route_message


def test_subscribe_messages_cover_all_channels():
    msgs = subscribe_messages("HYPE")
    types = {m["subscription"]["type"] for m in msgs}
    assert types == {"candle", "trades", "l2Book", "activeAssetCtx"}
    assert all(m["method"] == "subscribe" for m in msgs)
    candle = next(m for m in msgs if m["subscription"]["type"] == "candle")
    assert candle["subscription"]["interval"] == "1m"


def test_route_candle():
    msg = {"channel": "candle", "data": {"t": 1000, "T": 1059, "s": "HYPE", "i": "1m",
           "o": "1", "c": "2", "h": "3", "l": "0.5", "v": "9", "n": 4}}
    kind, items = route_message(msg)
    assert kind == "candle"
    assert items[0]["c"] == 2.0


def test_route_trades_returns_list():
    msg = {"channel": "trades", "data": [
        {"coin": "HYPE", "side": "B", "px": "62.0", "sz": "1000", "time": 5,
         "hash": "0x", "tid": 7, "users": []}]}
    kind, items = route_message(msg)
    assert kind == "trade"
    assert items[0]["is_large"] is True


def test_route_book():
    msg = {"channel": "l2Book", "data": {"coin": "HYPE", "time": 9,
           "levels": [[{"px": "1", "sz": "2", "n": 1}], [{"px": "2", "sz": "3", "n": 1}]]}}
    kind, payload = route_message(msg)
    assert kind == "book"
    assert payload["ts"] == 9
    assert payload["bids"][0]["px"] == "1"


def test_route_ctx():
    msg = {"channel": "activeAssetCtx", "data": {"coin": "HYPE", "ctx": {
        "funding": "0.0001", "openInterest": "10", "prevDayPx": "56", "dayNtlVlm": "1",
        "premium": "0", "oraclePx": "62.1", "markPx": "62.0", "midPx": "62.05"}}}
    kind, payload = route_message(msg)
    assert kind == "ctx"
    assert payload["mark_px"] == 62.0


def test_route_ignores_subscription_response():
    assert route_message({"channel": "subscriptionResponse", "data": {}}) == ("ignore", None)
