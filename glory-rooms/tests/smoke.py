"""
Glory Modes smoke test.

Hits the live proxy at http://localhost:8082. Requires:
- LM Studio running on :1234 with google/gemma-4-e4b loaded
- OpenRouter API key configured (env or ~/lm-proxy-config.json)
- Proxy running (python D:/Glory/glory-rooms/proxy/lm-proxy.py)

Usage:  python D:/Glory/glory-rooms/tests/smoke.py
Exit 0 = all green.
"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8082"
TIMEOUT = 600  # Kimi Thinking can be slow

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"


def http(method, path, body=None, expect=200):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            payload = json.loads(resp.read())
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
        try:
            payload = json.loads(e.read())
        except Exception:
            payload = {"error": "non-JSON response"}
    dt = int((time.monotonic() - t0) * 1000)
    return code, payload, dt


tests_passed = 0
tests_failed = 0


def test(name, fn):
    global tests_passed, tests_failed
    print(f"  {YELLOW}...{RESET} {name}", end="", flush=True)
    try:
        fn()
        tests_passed += 1
        print(f"\r  {GREEN}OK {RESET} {name}")
    except AssertionError as e:
        tests_failed += 1
        print(f"\r  {RED}FAIL{RESET} {name}\n      {e}")
    except Exception as e:
        tests_failed += 1
        print(f"\r  {RED}FAIL{RESET} {name}\n      unexpected: {e}")


print(f"\nGlory Modes smoke @ {BASE}\n")

# 1. /v1/models lists kimi + gemma
def t1():
    code, body, _ = http("GET", "/v1/models")
    assert code == 200, f"got {code}: {body}"
    ids = sorted(m["id"] for m in body["models"])
    assert "kimi" in ids and "gemma" in ids, f"missing models: {ids}"
test("GET /v1/models lists kimi + gemma", t1)

# 2. solo gemma
def t2():
    code, body, _ = http("POST", "/v1/messages",
        {"model": "gemma", "messages": [{"role": "user", "content": "Say the word pong."}],
         "max_tokens": 64})
    assert code == 200, f"got {code}: {body}"
    text = body["content"][0]["text"].lower()
    assert "pong" in text, f"no pong in: {text!r}"
test("solo gemma says pong", t2)

# 3. solo kimi
def t3():
    code, body, _ = http("POST", "/v1/messages",
        {"model": "kimi", "messages": [{"role": "user", "content": "Say the word pong."}],
         "max_tokens": 256})
    assert code == 200, f"got {code}: {body}"
    text = body["content"][0]["text"].lower()
    assert "pong" in text, f"no pong in: {text[:200]!r}"
test("solo kimi says pong", t3)

# 4. pipeline kimi -> gemma -> kimi
pipeline_session = {}
def t4():
    code, body, _ = http("POST", "/v1/pipeline", {
        "input": "Write a haiku about SQLite.",
        "steps": [
            {"model": "gemma", "system": "Write a haiku."},
            {"model": "gemma", "system": "Critique the haiku in one sentence."},
            {"model": "gemma", "system": "Rewrite the haiku improving on the critique."},
        ],
        "max_tokens_per_step": 256,
    })
    assert code == 200, f"got {code}: {body}"
    assert "session_id" in body
    assert len(body["trace"]) == 3, f"expected 3 trace entries, got {len(body['trace'])}"
    assert body["output"], "empty output"
    pipeline_session["id"] = body["session_id"]
test("pipeline: gemma x3 produces 3-entry trace", t4)

# 5. room kimi+gemma 4 turns
room_session = {}
def t5():
    code, body, _ = http("POST", "/v1/room", {
        "topic": "Should we use Postgres or SQLite for a single-user dev tool?",
        "participants": [
            {"model": "gemma", "name": "Min", "persona": "minimalist who hates dependencies"},
            {"model": "gemma", "name": "Pro", "persona": "pragmatic backend engineer"},
        ],
        "turns": 4,
        "max_tokens_per_turn": 256,
    })
    assert code == 200, f"got {code}: {body}"
    assert len(body["transcript"]) == 4, f"expected 4 turns, got {len(body['transcript'])}"
    speakers = [t["speaker"] for t in body["transcript"]]
    assert speakers == ["Min", "Pro", "Min", "Pro"], f"alternation wrong: {speakers}"
    room_session["id"] = body["session_id"]
test("room: 4 turns alternate Min/Pro", t5)

# 6. debate (kimi vs gemma — realistic parallel mix)
def t6():
    code, body, _ = http("POST", "/v1/debate", {
        "prompt": "Single-file Python script vs structured package - for a 500-line tool?",
        "participants": [
            {"model": "kimi",  "name": "Mono", "stance": "argue for single-file"},
            {"model": "gemma", "name": "Modu", "stance": "argue for structured package"},
        ],
        "synthesizer": {"model": "gemma", "instruction": "Pick the winner. One paragraph."},
        "max_tokens": 384,
    })
    assert code == 200, f"got {code}: {body}"
    assert len(body["answers"]) == 2, "need 2 answers"
    for a in body["answers"]:
        assert a["text"], f"empty answer for {a['model']}"
    assert body["synthesis"]["text"], "empty synthesis"
test("debate: 2 answers + 1 synthesis", t6)

# 7. GET session
def t7():
    sid = room_session["id"]
    code, body, _ = http("GET", f"/v1/sessions/{sid}")
    assert code == 200, f"got {code}: {body}"
    assert body["mode"] == "room"
    assert len(body["messages"]) == 4
test("GET /v1/sessions/<room_id> returns transcript", t7)

# 8. continue room
def t8():
    sid = room_session["id"]
    code, body, _ = http("POST", f"/v1/sessions/{sid}/continue", {"turns": 2})
    assert code == 200, f"got {code}: {body}"
    assert len(body["transcript"]) == 6, f"expected 6 turns, got {len(body['transcript'])}"
test("continue room +2 turns -> 6 total", t8)

# 9. pipeline with unknown model -> 400
def t9():
    code, body, _ = http("POST", "/v1/pipeline", {
        "input": "x",
        "steps": [{"model": "blarg", "system": "hi"}],
    })
    assert code == 502 or code == 400, f"got {code}: {body}"
    # Either 400 (rejected at validation) or 502 (rejected at backend dispatch).
    msg = json.dumps(body).lower()
    assert "blarg" in msg or "unknown" in msg, f"no useful error: {body}"
test("pipeline with unknown model errors", t9)

# 10. GET nonexistent session -> 404
def t10():
    code, body, _ = http("GET", "/v1/sessions/ses_doesnotexist")
    assert code == 404, f"got {code}: {body}"
    assert body["error"]["kind"] == "not_found"
test("GET nonexistent session -> 404", t10)


total = tests_passed + tests_failed
color = GREEN if tests_failed == 0 else RED
print(f"\n{color}{tests_passed}/{total} passed{RESET}")
sys.exit(0 if tests_failed == 0 else 1)
