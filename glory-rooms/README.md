# Glory Modes

Multi-model conversation environment. Local proxy + browser UI.

## What it does

Four conversation shapes across multiple LLM backends:

- **Solo** — one model, one prompt
- **Pipeline** — sequential chain; each step's output feeds the next
- **Room** — round-robin dialog where everyone sees the full transcript
- **Debate** — parallel fan-out, then a synthesizer picks/merges

Backends today: **Kimi K2.6** (OpenRouter, cloud) and **Gemma 4** (LM Studio, local).
New backends plug in with one wrapper + one registry entry.

## Layout

```
glory-rooms/
├── proxy/            Python HTTP proxy on :8082 (stdlib only, no deps)
│   ├── lm-proxy.py
│   └── run.bat       Windows launcher
├── ui/               Vite + React + TS, Tailwind. Dev on :5173
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       ├── components/
│       └── modes/    Solo, Pipeline, Room, Debate, SessionDetail
└── tests/
    └── smoke.py      End-to-end test (10 cases, hits live backends)
```

## Run it

**Prereqs.** LM Studio on `:1234` with `google/gemma-4-e4b` loaded.
OpenRouter key in `~/lm-proxy-config.json` or `OPENROUTER_API_KEY` env var.

**1. Start the proxy:**
```
python D:/Glory/glory-rooms/proxy/lm-proxy.py
```
Serves on `http://localhost:8082`. Sessions persist to `~/.claude-mem/glory-rooms.db`.

**2. Start the UI:**
```
cd D:/Glory/glory-rooms/ui
npm install        # first time only
npm run dev
```
Open `http://localhost:5173`. Vite proxies `/v1/*` to the proxy.

**3. Verify:**
```
python D:/Glory/glory-rooms/tests/smoke.py
```
All 10 tests should pass.

## API

| Endpoint                          | Method | Purpose                       |
|-----------------------------------|--------|-------------------------------|
| `/v1/messages`                    | POST   | Anthropic-format solo         |
| `/v1/pipeline`                    | POST   | sequential chain              |
| `/v1/room`                        | POST   | round-robin dialog            |
| `/v1/debate`                      | POST   | parallel + synthesizer        |
| `/v1/sessions`                    | GET    | list sessions                 |
| `/v1/sessions/:id`                | GET    | inspect a session             |
| `/v1/sessions/:id/continue`       | POST   | resume pipeline/room/solo     |
| `/v1/models`                      | GET    | registered backends           |

See `docs/superpowers/specs/2026-05-03-glory-modes-design.md` for the design.

## Adding a backend

In `proxy/lm-proxy.py`:

```python
def myprovider_call(model_id, messages, max_tokens=1024, temperature=1.0):
    # call your endpoint, return {"text", "raw", "tokens_in", "tokens_out", "latency_ms"}
    ...

BACKENDS["myname"] = {
    "backend": "myprovider",
    "underlying": "myprovider/model-id",
    "call": lambda msgs, **opts: myprovider_call("myprovider/model-id", msgs, **opts),
}
```

That's it. No request-shape changes.
