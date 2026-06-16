# Glory Modes — Multi-Model Conversation Environment

**Status:** Design — pending implementation plan
**Date:** 2026-05-03
**Owner:** losinglory
**Surface:** extension of `lm-proxy.py` on `:8082`

## 1. Purpose

Give Claude (and any HTTP client) a single local environment for talking to multiple LLM backends in four conversation shapes:

- **Solo** — one model, one prompt (already exists as `POST /v1/messages`).
- **Pipeline** — sequential chain; each step's output feeds the next.
- **Room** — turn-taking dialog where every participant sees the full transcript.
- **Debate** — parallel fan-out, then a synthesizer picks/merges.

In scope today: **Kimi K2.6** (via OpenRouter) and **Gemma 4** (via local LM Studio). The design adds a backend registry so new models (Gemini, Claude-as-participant, Ruflo) plug in with one entry + one wrapper function.

## 2. Architecture

Single Python process, single port, four orchestrators on top of one backend registry.

```
┌─────────────────────── lm-proxy.py :8082 ───────────────────────┐
│                                                                  │
│   Endpoints                                                      │
│     POST /v1/messages       (existing — solo, unchanged)         │
│     POST /v1/pipeline                                             │
│     POST /v1/room                                                 │
│     POST /v1/debate                                               │
│     POST /v1/sessions/:id/continue                                │
│     GET  /v1/sessions/:id                                         │
│     GET  /v1/models                                               │
│                                                                  │
│   Core                                                           │
│     ┌──────────────┐    ┌──────────────────────┐                │
│     │ Backend      │ →  │ call_backend(name,   │                │
│     │ registry     │    │   messages, opts)    │                │
│     └──────────────┘    └──────────┬───────────┘                │
│   Modes ───────────────────────────┘                            │
│     • solo / pipeline / room / debate                            │
│                                                                  │
│   Storage                                                        │
│     ~/.claude-mem/glory-rooms.db  (SQLite, stdlib)               │
│       sessions(id, mode, created_at, updated_at, meta)           │
│       messages(session_id, turn_idx, speaker, model, role,       │
│                content, raw, tokens_in/out, latency_ms, error)   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
              │                                  │
              ▼                                  ▼
   ┌────────────────────┐            ┌─────────────────────┐
   │ OpenRouter (Kimi)  │            │ LM Studio (Gemma)   │
   │ external           │            │ localhost:1234      │
   └────────────────────┘            └─────────────────────┘
```

## 3. API contracts

All bodies are JSON. `session_id` is optional everywhere — omit for one-shot, include to attach to or resume a stored session.

### 3.1 Solo — `POST /v1/messages` (existing, unchanged)

Anthropic-format request. `model` accepts `"kimi"` or `"gemma"` (registry-backed).

### 3.2 Pipeline — `POST /v1/pipeline`

```jsonc
{
  "input": "Design a SQLite schema for ...",
  "steps": [
    { "model": "kimi",  "system": "You're a DB architect. Draft." },
    { "model": "gemma", "system": "You're a critic. Find flaws." },
    { "model": "kimi",  "system": "Architect. Revise per the critique." }
  ],
  "max_tokens_per_step": 1024,           // default; each step may override with its own "max_tokens"
  "session_id": null
}
→ {
  "session_id": "ses_abc12345",
  "output": "<final step text>",
  "trace": [{ "step": 0, "model": "kimi", "text": "..." }, ...]
}
```

### 3.3 Room — `POST /v1/room`

```jsonc
{
  "topic": "Postgres or SQLite for this?",
  "participants": [
    { "model": "kimi",  "name": "K", "persona": "pragmatic backend eng" },
    { "model": "gemma", "name": "G", "persona": "minimalist, hates deps" }
  ],
  "turns": 6,
  "order": "round_robin",
  "max_tokens_per_turn": 512,
  "session_id": null
}
→ {
  "session_id": "ses_xyz98765",
  "transcript": [{ "turn": 0, "speaker": "K", "model": "kimi", "text": "..." }, ...]
}
```

### 3.4 Debate — `POST /v1/debate`

```jsonc
{
  "prompt": "Best multi-model orchestrator architecture?",
  "participants": [
    { "model": "kimi",  "stance": "argue for microservices" },
    { "model": "gemma", "stance": "argue for monolith" }
  ],
  "synthesizer": {
    "model": "kimi",
    "instruction": "Pick the winner, or merge if both have merit."
  },
  "max_tokens": 1024,
  "session_id": null
}
→ {
  "session_id": "ses_dbg00001",
  "answers":   [{ "model": "kimi",  "stance": "...", "text": "..." }, ...],
  "synthesis": { "model": "kimi", "text": "Final verdict..." }
}
```

### 3.5 Continuation — `POST /v1/sessions/:id/continue`

Body shape depends on `session.mode`:

| Mode | Body | Behavior |
|---|---|---|
| `pipeline` | `{ "steps": [...] }` | append and run new steps |
| `room` | `{ "turns": N }` | continue round-robin for N more turns |
| `solo` | `{ "message": "..." }` | one more user → assistant turn |
| `debate` | — | 400; debates are one-shot |

`/continue` does not change participants, persona/stance, topic, or synthesizer — those are fixed at session creation and stored in `meta`. To change them, start a new session.

### 3.6 Inspect & list — `GET /v1/sessions/:id`, `GET /v1/models`

```jsonc
GET /v1/sessions/ses_xyz98765
→ {
  "id": "ses_xyz98765",
  "mode": "room",
  "created_at": "2026-05-03T20:15:00Z",
  "updated_at": "2026-05-03T20:18:42Z",
  "meta": { "topic": "...", "participants": [...] },
  "messages": [
    { "turn_idx": 0, "speaker": "K", "model": "kimi",  "role": "assistant",
      "content": "...", "tokens_in": 120, "tokens_out": 80, "latency_ms": 600 },
    ...
  ]
}
```

The `messages` array is the canonical record. Mode-specific endpoints expose it under friendlier names (`trace` for pipeline, `transcript` for room, `answers`+`synthesis` for debate) — same underlying rows.

```jsonc
GET /v1/models
→ {
  "models": [
    { "id": "kimi",  "backend": "openrouter", "underlying": "moonshotai/kimi-k2-thinking" },
    { "id": "gemma", "backend": "lm-studio",  "underlying": "google/gemma-4-e4b" }
  ]
}
```

## 4. Mode semantics (orchestration logic)

### 4.1 Pipeline

```
load_or_create_session(mode="pipeline")
prior = input
for i, step in enumerate(steps):
    msgs = [{role:"system", content: step.system},
            {role:"user",   content: prior}]
    resp = call_backend(step.model, msgs, max_tokens=step.max_tokens or default)
    save_message(session_id, turn=i, speaker=step.model, text=resp.text)
    prior = resp.text
return { session_id, output: prior, trace: all_messages }
```

If a step fails, the response includes the partial trace plus the error. The session is preserved; `/continue` resumes from the last successful turn.

### 4.2 Room

```
load_or_create_session(mode="room")
start = len(existing_transcript)
for t in range(start, start + turns):
    speaker = participants[t % len(participants)]
    msgs = [{role:"system",
             content: f"You are {speaker.name}. {speaker.persona}\nTopic: {topic}"}]
    for m in transcript:
        role = "assistant" if m.speaker == speaker.name else "user"
        msgs.append({role, content: f"[{m.speaker}]: {m.text}"})
    resp = call_backend(speaker.model, msgs, max_tokens=...)
    save_message(session_id, turn=t, speaker=speaker.name, text=resp.text)
return { session_id, transcript }
```

The trick that makes multi-party dialog work on 2-role chat APIs: the speaker's own past messages are mapped to `assistant`, everyone else's to `user` with a `[Name]:` prefix. The system prompt anchors persona + topic.

Resume reads `mode` from the session and picks up at the next round-robin slot.

### 4.3 Debate

```
# Phase 1: parallel
answers = parallel_map(participants, lambda p:
    call_backend(p.model,
                 [{role:"system", content: f"Stance: {p.stance}"},
                  {role:"user",   content: prompt}],
                 max_tokens))
# save each as turn 0..N-1

# Phase 2: synthesize
msgs = [{role:"system", content: synthesizer.instruction},
        {role:"user",   content: f"Prompt: {prompt}\n\n" +
                                 "\n".join(f"[{p.name}]: {a.text}"
                                           for p,a in zip(participants, answers))
                                 + "\n\nSynthesize."}]
synthesis = call_backend(synthesizer.model, msgs, max_tokens)
# save as turn N
return { session_id, answers, synthesis }
```

Phase 1 fan-out uses `concurrent.futures.ThreadPoolExecutor(max_workers=len(participants))`.

### 4.4 Backend registry

```python
BACKENDS = {
    "kimi":  lambda msgs, **opts: openrouter_call("moonshotai/kimi-k2-thinking", msgs, **opts),
    "gemma": lambda msgs, **opts: lmstudio_call("google/gemma-4-e4b", msgs, **opts),
}

def call_backend(name, msgs, **opts):
    if name not in BACKENDS:
        raise BackendError(f"unknown model: {name}")
    return BACKENDS[name](msgs, **opts)  # → {text, raw, tokens, latency_ms}
```

Adding a new backend later = one entry + one wrapper function. No request shape changes.

## 5. Storage

SQLite at `~/.claude-mem/glory-rooms.db` — stdlib only, sits next to `claude-mem.db` for backup convenience.

```sql
CREATE TABLE sessions (
  id          TEXT PRIMARY KEY,            -- "ses_a1b2c3d4"
  mode        TEXT NOT NULL,               -- solo | pipeline | room | debate
  created_at  TEXT NOT NULL,               -- ISO 8601 UTC
  updated_at  TEXT NOT NULL,
  meta        TEXT NOT NULL DEFAULT '{}'   -- JSON: topic, participants, original request
);

CREATE TABLE messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  turn_idx    INTEGER NOT NULL,
  speaker     TEXT NOT NULL,               -- name (room) or model id (other modes)
  model       TEXT NOT NULL,               -- backend id: kimi | gemma | ...
  role        TEXT NOT NULL,               -- system | user | assistant
  content     TEXT NOT NULL,
  raw         TEXT,                        -- full backend response JSON
  tokens_in   INTEGER,
  tokens_out  INTEGER,
  latency_ms  INTEGER,
  error       TEXT,                        -- nullable; populated only if this turn failed
  created_at  TEXT NOT NULL
);

CREATE INDEX idx_messages_session ON messages(session_id, turn_idx);
```

- IDs: `ses_` + 8 hex chars.
- `meta` stores a snapshot of the original request (topic, participants with personas/stances) so resumed sessions know who's who.

## 6. Concurrency

- Single Python process, threaded HTTP server (existing pattern).
- Pipeline + room: sequential calls.
- Debate: `ThreadPoolExecutor(max_workers=len(participants))`.
- Per-session lock: `dict[str, threading.Lock]`, lazy-init. Two `/continue` calls on the same `session_id` serialize.

## 7. Error handling

| Failure | HTTP | Body |
|---|---|---|
| Bad request (unknown model, missing field) | 400 | `{error: {kind:"bad_request", message}}` |
| Session not found | 404 | `{error: {kind:"not_found"}}` |
| Backend down / network / timeout | 502 | partial trace + `{error: {kind:"backend", step, model, message, resumable: true}}` |
| Backend rate-limited | 429 | retry once with 2s backoff; if still 429, surface as 429 |
| Internal | 500 | `{error: {kind:"internal", message}}` |

**Mid-mode failure rule:** anything successfully computed before the failure is saved. The response includes the partial trace plus the error. `/continue` resumes from the last successful turn — no work is lost.

**Per-call timeouts (env-configurable):** Gemma local 60s, Kimi via OpenRouter 120s.

## 8. Logging

Reuse the existing `safe_print` pattern from `lm-proxy.py`. One log line per request:

```
mode=room session=ses_xyz98765 model=kimi step=3 latency_ms=842 tokens_in=512 tokens_out=128 status=ok
```

No new logging dependencies.

## 9. Testing

Single `tests/smoke.py` script — no test framework. Hits the real backends end-to-end (~30–60s).

```
1.  GET  /v1/models                         → 200, lists kimi + gemma
2.  POST /v1/messages  kimi  "say pong"     → response contains "pong"
3.  POST /v1/messages  gemma "say pong"     → response contains "pong"
4.  POST /v1/pipeline  (kimi → gemma → kimi)→ trace has 3 entries, output non-empty
5.  POST /v1/room      (kimi+gemma, 4 turns)→ transcript has 4 turns, alternating
6.  POST /v1/debate    (kimi vs gemma, kimi)→ 2 answers + 1 synthesis, all non-empty
7.  GET  /v1/sessions/<room_id>             → returns transcript from step 5
8.  POST /v1/sessions/<room_id>/continue {turns:2}
                                            → transcript now has 6 turns
9.  POST /v1/pipeline  with model "blarg"   → 400, kind:"bad_request"
10. GET  /v1/sessions/ses_doesnotexist      → 404, kind:"not_found"
```

Exit 0 = green.

## 10. Rollout

1. Build behind feature flag `GLORY_MODES_ENABLED=1`. Off → only `/v1/messages` is mounted (today's behavior).
2. Run smoke tests with the flag on.
3. Flip the flag in the running service. Existing endpoint untouched.
4. Rollback = unset flag, restart.

## 11. Out of scope (deferred)

- **Streaming (SSE)** — modes return full responses only. Add later if interactive UX demands it.
- **Authentication** — same trust model as today (localhost only, no auth).
- **Concurrency stress / rate limiting** — single-user local tool; not a server product.
- **Additional backends** — Gemini, Claude-as-participant, Ruflo. Plug-in path is reserved by the registry; spec'd in a follow-up.
- **Moderated / free-form room order** — only `round_robin` lands today; `moderated` and `free` are a future extension.
- **Streaming partial results from the backend** — modes either return a full response or surface an error; no incremental streaming.

## 12. Success criteria

The design is implemented correctly when:

1. Existing `/v1/messages` behavior is bit-for-bit unchanged (no regressions in Claude Code's current routing).
2. All 10 smoke tests pass against the live Kimi + Gemma backends.
3. A failed mid-mode call leaves a resumable session — calling `/continue` on it produces a complete result.
4. Adding a new backend (e.g. a stub `echo` model that returns its input) takes ≤ 20 lines: one wrapper function + one registry entry, no other code changes.
