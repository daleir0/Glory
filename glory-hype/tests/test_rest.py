import json
import httpx
from glory_hype.hl_rest import RestClient


def _client(handler):
    transport = httpx.MockTransport(handler)
    return RestClient(http=httpx.Client(transport=transport))


def test_meta_and_asset_ctxs_extracts_hype():
    def handler(request):
        body = json.loads(request.content)
        assert body == {"type": "metaAndAssetCtxs"}
        payload = [
            {"universe": [{"name": "BTC"}, {"name": "HYPE"}]},
            [{"markPx": "1"}, {"funding": "0.0000125", "openInterest": "10",
                               "prevDayPx": "56", "dayNtlVlm": "1", "premium": "0",
                               "oraclePx": "62.1", "markPx": "62.0", "midPx": "62.05"}],
        ]
        return httpx.Response(200, json=payload)
    ctx = _client(handler).asset_ctx("HYPE")
    assert ctx["mark_px"] == 62.0


def test_candle_snapshot_parses_list():
    def handler(request):
        body = json.loads(request.content)
        assert body["type"] == "candleSnapshot"
        assert body["req"]["coin"] == "HYPE"
        return httpx.Response(200, json=[
            {"t": 1000, "T": 1059, "s": "HYPE", "i": "1m", "o": "1", "c": "2",
             "h": "3", "l": "0.5", "v": "9", "n": 4}])
    candles = _client(handler).candle_snapshot("HYPE", "1m", 0, 60000)
    assert len(candles) == 1
    assert candles[0]["c"] == 2.0
