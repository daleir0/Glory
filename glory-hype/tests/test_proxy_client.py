import json
import httpx
import pytest
from glory_hype.narrative.proxy_client import ProxyClient, ProxyError


def _client(handler):
    return ProxyClient(base_url="http://proxy", model="claude",
                       http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_chat_returns_text():
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "claude"
        assert body["messages"][0]["content"] == "hi"
        return httpx.Response(200, json={"choices": [
            {"message": {"content": "the answer"}}]})
    assert _client(handler).chat([{"role": "user", "content": "hi"}]) == "the answer"


def test_chat_raises_on_http_error():
    def handler(request):
        return httpx.Response(500, text="boom")
    with pytest.raises(ProxyError):
        _client(handler).chat([{"role": "user", "content": "hi"}])
