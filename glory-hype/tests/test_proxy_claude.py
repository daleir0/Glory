import importlib.util
import io
import json
from pathlib import Path

import pytest

PROXY = Path("E:/Glory/glory-rooms/proxy/lm-proxy.py")


def load_proxy(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    spec = importlib.util.spec_from_file_location("lm_proxy", PROXY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_anthropic_call_parses_text(monkeypatch):
    mod = load_proxy(monkeypatch)
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
        captured["body"] = json.loads(req.data)
        return FakeResp({"content": [{"type": "text", "text": "hello from claude"}]})

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    text = mod.anthropic_call("claude-opus-4-8",
                              [{"role": "user", "content": "hi"}], max_tokens=50)
    assert text == "hello from claude"
    assert "api.anthropic.com" in captured["url"]
    assert captured["headers"]["x-api-key"] == "test-key"
    assert "anthropic-version" in captured["headers"]
    assert captured["body"]["messages"][0]["content"] == "hi"


def test_call_backend_routes_claude(monkeypatch):
    mod = load_proxy(monkeypatch)
    monkeypatch.setattr(mod, "anthropic_call", lambda m, msgs, **o: "routed-claude")
    out = mod.call_backend("claude", [{"role": "user", "content": "x"}])
    # call_backend returns a response dict with text; check it surfaced our value
    assert "routed-claude" in json.dumps(out)


def test_anthropic_call_missing_key(monkeypatch):
    mod = load_proxy(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(mod, "get_anthropic_key", lambda: "")
    with pytest.raises(mod.BackendError):
        mod.anthropic_call("claude-opus-4-8", [{"role": "user", "content": "hi"}])


def test_select_backend_routes_claude(monkeypatch):
    mod = load_proxy(monkeypatch)
    assert mod.select_backend("claude") == "claude"
    assert mod.select_backend("opus") == "claude"
    assert mod.select_backend("kimi") == "kimi"
    assert mod.select_backend("qwen") == "qwen"
    assert mod.select_backend("anything-else") == "gemma"


def test_claude_backend_returns_openai_envelope(monkeypatch):
    mod = load_proxy(monkeypatch)
    monkeypatch.setattr(mod, "anthropic_call", lambda m, msgs, **o: "hello")
    out = mod.BACKENDS["claude"]["call"]([{"role": "user", "content": "hi"}])
    assert out["text"] == "hello"
    assert out["raw"]["choices"][0]["message"]["content"] == "hello"
