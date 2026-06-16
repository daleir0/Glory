from unittest.mock import MagicMock, patch
from glory_hype.narrative.synthesize import Synthesizer
from glory_hype import config


def _make_store(tmp_path):
    from glory_hype.db import Store
    s = Store(str(tmp_path / "t.db"))
    import time
    now = int(time.time() * 1000)
    s.insert_ctx({"funding": 0.0001, "open_interest": 1e6, "mark_px": 70.0,
                  "oracle_px": 70.0, "mid_px": 70.0, "premium": 0.0,
                  "prev_day_px": 68.0, "day_ntl_vlm": 1e9}, ts=now)
    return s


def test_default_synthesizer_uses_lm_studio(tmp_path):
    store = _make_store(tmp_path)
    with patch("glory_hype.narrative.synthesize.ProxyClient") as MockProxy:
        mock_instance = MagicMock()
        mock_instance.chat.return_value = (
            '{"bias":"bullish","confidence":0.7,"key_drivers":["test"],'
            '"caution_flags":[],"source_breakdown":{}}'
        )
        MockProxy.return_value = mock_instance
        syn = Synthesizer(store)
        syn.synthesize()
        MockProxy.assert_called_once_with(
            base_url=config.LM_STUDIO_URL,
            model=config.LM_STUDIO_MODEL
        )


def test_explicit_proxy_overrides_default(tmp_path):
    store = _make_store(tmp_path)
    custom_proxy = MagicMock()
    custom_proxy.chat.return_value = (
        '{"bias":"neutral","confidence":0.5,"key_drivers":[],'
        '"caution_flags":[],"source_breakdown":{}}'
    )
    with patch("glory_hype.narrative.synthesize.ProxyClient") as MockProxy:
        syn = Synthesizer(store, proxy=custom_proxy)
        syn.synthesize()
        MockProxy.assert_not_called()
        custom_proxy.chat.assert_called_once()


def test_proxy_error_returns_unavailable(tmp_path):
    from glory_hype.narrative.proxy_client import ProxyError
    store = _make_store(tmp_path)
    bad_proxy = MagicMock()
    bad_proxy.chat.side_effect = ProxyError("connection refused")
    syn = Synthesizer(store, proxy=bad_proxy)
    c = syn.synthesize()
    assert c.bias == "neutral"
    assert any("unavailable" in f.lower() for f in c.caution_flags)
