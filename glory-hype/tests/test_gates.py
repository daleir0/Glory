from glory_hype.decision.gates import evaluate_gates
from glory_hype import config

NOW = 1_000_000_000_000


def _ctx(ts=NOW):
    return {"ts": ts, "mark_px": 67.5}


def _conc(at=NOW, bias="bullish", conf=0.7, cautions=None):
    return {"generated_at": at, "bias": bias, "confidence": conf,
            "caution_flags": cautions or []}


def _chart(flags=None, position=None):
    return {"flags": flags or [], "trend": "range", "current_price": 67.5,
            "position": position or {"entry": 67.4, "sl": 66.7, "tp": 68.2}}


def test_all_pass_returns_empty():
    assert evaluate_gates(_ctx(), _conc(), _chart(), NOW, config) == []


def test_missing_chart_read():
    g = evaluate_gates(_ctx(), _conc(), None, NOW, config)
    assert any("chart" in x.lower() for x in g)


def test_flagged_chart():
    g = evaluate_gates(_ctx(), _conc(), _chart(flags=["diverges 33%"]), NOW, config)
    assert any("flag" in x.lower() for x in g)


def test_stale_ctx():
    old = NOW - config.CTX_STALE_MS - 1
    g = evaluate_gates(_ctx(ts=old), _conc(), _chart(), NOW, config)
    assert any("market data" in x.lower() or "ctx" in x.lower() for x in g)


def test_stale_narrative():
    old = NOW - config.NARRATIVE_STALE_MS - 1
    g = evaluate_gates(_ctx(), _conc(at=old), _chart(), NOW, config)
    assert any("narrative" in x.lower() and "stale" in x.lower() for x in g)


def test_unavailable_narrative():
    g = evaluate_gates(_ctx(), _conc(cautions=["synthesis unavailable"]), _chart(), NOW, config)
    assert any("unavailable" in x.lower() for x in g)


def test_missing_narrative():
    g = evaluate_gates(_ctx(), None, _chart(), NOW, config)
    assert any("narrative" in x.lower() for x in g)


def test_missing_ctx():
    g = evaluate_gates(None, _conc(), _chart(), NOW, config)
    assert any("market data" in x.lower() for x in g)
