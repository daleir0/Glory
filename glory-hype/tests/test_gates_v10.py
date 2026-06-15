from glory_hype.decision.gates import evaluate_gates
from glory_hype import config
from glory_hype.db import Store

NOW = 1_000_000_000_000


def _ctx(ts=NOW):
    return {"ts": ts, "mark_px": 70.0}


def _conc(at=NOW, bias="bullish", cautions=None):
    return {"generated_at": at, "bias": bias, "confidence": 0.7,
            "caution_flags": cautions or [], "score": 70}


def _chart():
    return {"flags": [], "trend": "up", "current_price": 70.0}


def test_default_stale_threshold_is_12h():
    old = NOW - (12 * 3600 * 1000) - 1
    g = evaluate_gates(_ctx(), _conc(at=old), _chart(), NOW, config, store=None)
    assert any("stale" in x.lower() for x in g)


def test_within_12h_passes():
    recent = NOW - (11 * 3600 * 1000)
    g = evaluate_gates(_ctx(), _conc(at=recent), _chart(), NOW, config, store=None)
    assert not any("stale" in x.lower() for x in g)


def test_settings_override_stale_threshold(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("synthesis_stale_hours", "4")
    old = NOW - (5 * 3600 * 1000)  # 5h ago — stale with 4h override, fine with 12h default
    g = evaluate_gates(_ctx(), _conc(at=old), _chart(), NOW, config, store=s)
    assert any("stale" in x.lower() for x in g)


def test_settings_override_allows_older_if_looser(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("synthesis_stale_hours", "24")
    old = NOW - (20 * 3600 * 1000)  # 20h ago — fine with 24h override
    g = evaluate_gates(_ctx(), _conc(at=old), _chart(), NOW, config, store=s)
    assert not any("stale" in x.lower() for x in g)
