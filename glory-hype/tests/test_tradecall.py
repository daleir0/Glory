from glory_hype.decision.tradecall import TradeCall, parse_judgment, no_trade


def test_parse_valid_judgment():
    j = parse_judgment({"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                        "confidence": 0.7, "rationale": "aligned"})
    assert j["decision"] == "long"
    assert j["entry"] == 67.4 and j["tp"] == 68.2 and j["sl"] == 66.7
    assert j["confidence"] == 0.7


def test_parse_clamps_confidence_and_validates_decision():
    j = parse_judgment({"decision": "sideways", "entry": 1, "tp": 2, "sl": 0.5,
                        "confidence": 5})
    assert j["decision"] == "no_trade"      # invalid direction -> no_trade
    assert j["confidence"] == 1.0           # clamped


def test_parse_missing_levels_forces_no_trade():
    j = parse_judgment({"decision": "long", "entry": None, "tp": 68.2, "sl": 66.7})
    assert j["decision"] == "no_trade"
    assert "incomplete" in j["rationale"].lower()


def test_no_trade_factory():
    c = no_trade(["bad"], generated_at=5)
    assert c.decision == "no_trade"
    assert c.gates_failed == ["bad"]
    assert c.confidence == 0.0
    assert c.to_dict()["generated_at"] == 5


def test_tradecall_to_dict_roundtrips():
    c = TradeCall(decision="long", entry=67.4, tp=68.2, sl=66.7,
                  position_notional=100.0, position_coins=1.48, margin=10.0,
                  leverage=10, rr=1.19, liq_price=60.6, confidence=0.7,
                  rationale="x", gates_failed=[], inputs={"ctx_ts": 1}, generated_at=9)
    d = c.to_dict()
    assert d["decision"] == "long" and d["rr"] == 1.19 and d["inputs"]["ctx_ts"] == 1
