from glory_hype.db import Store
from glory_hype.verify import verify_ctx


class FakeRest:
    def __init__(self, mark):
        self._mark = mark

    def asset_ctx(self, coin):
        return {"funding": 0.0001, "open_interest": 10.0, "mark_px": self._mark,
                "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                "prev_day_px": 56.0, "day_ntl_vlm": 1.0}


def test_verify_passes_within_tolerance(tmp_path):
    s = Store(str(tmp_path / "v.db"))
    s.insert_ctx({"funding": 0.0001, "open_interest": 10.0, "mark_px": 62.00,
                  "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                  "prev_day_px": 56.0, "day_ntl_vlm": 1.0}, ts=1)
    ok, report = verify_ctx(s, FakeRest(62.01), tol_pct=0.5)
    assert ok is True


def test_verify_fails_outside_tolerance(tmp_path):
    s = Store(str(tmp_path / "v2.db"))
    s.insert_ctx({"funding": 0.0001, "open_interest": 10.0, "mark_px": 62.00,
                  "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                  "prev_day_px": 56.0, "day_ntl_vlm": 1.0}, ts=1)
    ok, report = verify_ctx(s, FakeRest(70.0), tol_pct=0.5)
    assert ok is False
    assert "mark_px" in report


def test_verify_no_data(tmp_path):
    s = Store(str(tmp_path / "v3.db"))
    ok, report = verify_ctx(s, FakeRest(62.0), tol_pct=0.5)
    assert ok is False
    assert "no stored" in report.lower()
