"""Thin client for the Glory proxy's OpenAI-compatible chat endpoint."""

import httpx


class ProxyError(Exception):
    pass


class ProxyClient:
    def __init__(self, base_url: str = "http://localhost:8082",
                 model: str = "claude", http: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http = http or httpx.Client(timeout=120.0)

    def chat(self, messages: list, max_tokens: int = 1500) -> str:
        try:
            r = self.http.post(
                f"{self.base_url}/v1/chat/completions",
                json={"model": self.model, "messages": messages,
                      "max_tokens": max_tokens})
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            raise ProxyError(str(e)) from e
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ProxyError(f"unexpected response shape: {data}") from e

    def close(self):
        self.http.close()
