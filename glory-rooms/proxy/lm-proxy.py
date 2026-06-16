"""
Glory proxy + Glory Modes (multi-model conversation environment).

Endpoints:
  POST /v1/messages              Anthropic-format solo (kimi or gemma)
  POST /v1/pipeline              sequential chain of model calls
  POST /v1/room                  round-robin multi-participant dialog
  POST /v1/debate                parallel fan-out + synthesizer
  GET  /v1/sessions/:id          inspect a stored session
  POST /v1/sessions/:id/continue resume a pipeline/room/solo session
  GET  /v1/models                list registered backends

Routing:
  model "kimi" / aliases  -> OpenRouter (cloud, moonshotai/kimi-k2.6)
  everything else         -> LM Studio  (local, google/gemma-4-e4b)

Run:   python D:/Glory/glory-rooms/proxy/lm-proxy.py
Then:  ANTHROPIC_BASE_URL=http://localhost:8082

OpenRouter key: OPENROUTER_API_KEY env var, or ~/lm-proxy-config.json
Sessions DB:    ~/.claude-mem/glory-rooms.db  (auto-created)
"""
import json
import os
import http.server
import traceback
import urllib.request
import urllib.error
import urllib.parse
import sqlite3
import threading
import weakref
import secrets
import time
import datetime
import socket
import subprocess
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LM_STUDIO_HOST  = os.environ.get("LM_STUDIO_HOST", "169.254.83.107")
LM_STUDIO_URL   = f"http://{LM_STUDIO_HOST}:1234/v1/chat/completions"
OPENROUTER_URL  = "https://openrouter.ai/api/v1/chat/completions"
LM_STUDIO_MODEL = "google/gemma-4-e4b"
QWEN_MODEL      = "qwen/qwen3.6-27b"
KIMI_MODEL      = "moonshotai/kimi-k2.6"
PORT            = 8082

KIMI_ALIASES  = {"kimi", "kimi-k2.6", "kimi-k2", "moonshotai/kimi-k2.6", "moonshotai/kimi-k2"}
QWEN_ALIASES  = {"qwen", "qwen3", "qwen3.6", "qwen3.6-27b", "qwen/qwen3.6-27b"}
GEMMA_ALIASES = {"gemma", "gemma-4", "gemma-4-e4b", "google/gemma-4-e4b", "local", "fast", "private"}

DB_PATH = os.path.expanduser("~/.claude-mem/glory-rooms.db")
GLORY_MODES_ENABLED = os.environ.get("GLORY_MODES_ENABLED", "1") != "0"

GEMMA_TIMEOUT = int(os.environ.get("GEMMA_TIMEOUT", "120"))
QWEN_TIMEOUT  = int(os.environ.get("QWEN_TIMEOUT", "120"))
KIMI_TIMEOUT  = int(os.environ.get("KIMI_TIMEOUT", "600"))


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def safe_print(msg):
    try:
        print(msg)
    except Exception:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def get_openrouter_key():
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        config_path = os.path.expanduser("~/lm-proxy-config.json")
        try:
            with open(config_path) as f:
                key = json.load(f).get("openrouter_api_key", "")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return key


def get_anthropic_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        cfg = os.path.expanduser("~/lm-proxy-config.json")
        if os.path.exists(cfg):
            with open(cfg) as f2:
                key = __import__('json').load(f2).get("anthropic_api_key", "")
    return key


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_session_id():
    return "ses_" + secrets.token_hex(4)


# ---------------------------------------------------------------------------
# Storage  (SQLite, stdlib)
# ---------------------------------------------------------------------------
_db_init_lock = threading.Lock()
_session_locks = weakref.WeakValueDictionary()
_session_locks_lock = threading.Lock()


def db():
    """Return a new sqlite3 connection. Caller closes."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)  # autocommit
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _db_init_lock:
        conn = db()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                  id          TEXT PRIMARY KEY,
                  mode        TEXT NOT NULL,
                  created_at  TEXT NOT NULL,
                  updated_at  TEXT NOT NULL,
                  meta        TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS messages (
                  id          INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                  turn_idx    INTEGER NOT NULL,
                  speaker     TEXT NOT NULL,
                  model       TEXT NOT NULL,
                  role        TEXT NOT NULL,
                  content     TEXT NOT NULL,
                  raw         TEXT,
                  tokens_in   INTEGER,
                  tokens_out  INTEGER,
                  latency_ms  INTEGER,
                  error       TEXT,
                  created_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session
                  ON messages(session_id, turn_idx);
                CREATE TABLE IF NOT EXISTS shared_memory (
                  key         TEXT PRIMARY KEY,
                  value       TEXT NOT NULL,
                  author      TEXT NOT NULL DEFAULT 'user',
                  tags        TEXT NOT NULL DEFAULT '[]',
                  created_at  TEXT NOT NULL,
                  updated_at  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_log (
                  id          TEXT PRIMARY KEY,
                  url         TEXT NOT NULL,
                  domain      TEXT NOT NULL,
                  status      INTEGER,
                  tech_stack  TEXT,
                  api_patterns TEXT,
                  obsidian_path TEXT,
                  scraped_at  TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS manual_schedules (
                  id          TEXT PRIMARY KEY,
                  title       TEXT NOT NULL,
                  cron        TEXT,
                  description TEXT,
                  created_at  TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS glory_tasks (
                  id          TEXT PRIMARY KEY,
                  name        TEXT NOT NULL,
                  prompt      TEXT NOT NULL,
                  schedule    TEXT,
                  enabled     INTEGER NOT NULL DEFAULT 1,
                  last_run    TEXT,
                  last_result TEXT,
                  run_count   INTEGER NOT NULL DEFAULT 0,
                  created_at  TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS agent_messages (
                  id          INTEGER PRIMARY KEY AUTOINCREMENT,
                  from_agent  TEXT NOT NULL,
                  to_agent    TEXT NOT NULL DEFAULT 'all',
                  content     TEXT NOT NULL,
                  thread      TEXT,
                  created_at  TEXT DEFAULT (datetime('now'))
                );
            """)
        finally:
            conn.close()


def session_lock(session_id):
    with _session_locks_lock:
        lock = _session_locks.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _session_locks[session_id] = lock
        return lock


def create_session(mode, meta):
    sid = new_session_id()
    ts = now_iso()
    conn = db()
    try:
        conn.execute(
            "INSERT INTO sessions(id, mode, created_at, updated_at, meta) VALUES (?,?,?,?,?)",
            (sid, mode, ts, ts, json.dumps(meta)),
        )
    finally:
        conn.close()
    return sid


def get_session(session_id):
    conn = db()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "mode": row["mode"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "meta": json.loads(row["meta"] or "{}"),
        }
    finally:
        conn.close()


def list_sessions(limit=50):
    conn = db()
    try:
        rows = conn.execute(
            "SELECT id, mode, created_at, updated_at, meta FROM sessions "
            "ORDER BY updated_at DESC LIMIT ?", (limit,),
        ).fetchall()
        out = []
        for r in rows:
            meta = json.loads(r["meta"] or "{}")
            out.append({
                "id": r["id"], "mode": r["mode"],
                "created_at": r["created_at"], "updated_at": r["updated_at"],
                "title": meta.get("topic") or meta.get("prompt") or meta.get("input") or "",
            })
        return out
    finally:
        conn.close()


def get_messages(session_id):
    conn = db()
    try:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY turn_idx, id",
            (session_id,),
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "turn_idx": r["turn_idx"],
                "speaker": r["speaker"],
                "model": r["model"],
                "role": r["role"],
                "content": r["content"],
                "tokens_in": r["tokens_in"],
                "tokens_out": r["tokens_out"],
                "latency_ms": r["latency_ms"],
                "error": r["error"],
                "created_at": r["created_at"],
            })
        return out
    finally:
        conn.close()


def list_memory(limit=200):
    conn = db()
    try:
        rows = conn.execute(
            "SELECT key, value, author, tags, created_at, updated_at "
            "FROM shared_memory ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"key": r["key"], "value": r["value"], "author": r["author"],
                 "tags": json.loads(r["tags"] or "[]"),
                 "created_at": r["created_at"], "updated_at": r["updated_at"]}
                for r in rows]
    finally:
        conn.close()


def upsert_memory(key, value, author="user", tags=None):
    ts = now_iso()
    tags_json = json.dumps(tags or [])
    conn = db()
    try:
        existing = conn.execute(
            "SELECT created_at FROM shared_memory WHERE key=?", (key,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE shared_memory SET value=?, author=?, tags=?, updated_at=? WHERE key=?",
                (value, author, tags_json, ts, key),
            )
            created_at = existing["created_at"]
        else:
            conn.execute(
                "INSERT INTO shared_memory(key, value, author, tags, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (key, value, author, tags_json, ts, ts),
            )
            created_at = ts
        return {"key": key, "value": value, "author": author,
                "tags": tags or [], "created_at": created_at, "updated_at": ts}
    finally:
        conn.close()


def delete_memory_key(key):
    conn = db()
    try:
        conn.execute("DELETE FROM shared_memory WHERE key=?", (key,))
    finally:
        conn.close()


def get_memory_context():
    entries = list_memory(100)
    if not entries:
        return ""
    lines = ["GLORY SHARED MIND (persistent cross-model memory):"]
    for e in entries:
        lines.append(f"  [{e['key']}]: {e['value']}")
    return "\n".join(lines)


def get_stats():
    conn = db()
    try:
        sessions_total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        rows = conn.execute(
            "SELECT model, COUNT(*) as msgs, "
            "COALESCE(SUM(tokens_in), 0) as tin, COALESCE(SUM(tokens_out), 0) as tout, "
            "COALESCE(AVG(latency_ms), 0) as avg_lat "
            "FROM messages GROUP BY model"
        ).fetchall()
        models_stats = []
        total_in = 0
        total_out = 0
        for r in rows:
            ti, to = int(r["tin"]), int(r["tout"])
            total_in += ti
            total_out += to
            models_stats.append({
                "model": r["model"],
                "messages": r["msgs"],
                "tokens_in": ti,
                "tokens_out": to,
                "avg_latency_ms": round(r["avg_lat"]),
            })
        return {
            "sessions_total": sessions_total,
            "models": models_stats,
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
        }
    finally:
        conn.close()


def append_message(session_id, turn_idx, speaker, model, role, content,
                   raw=None, tokens_in=0, tokens_out=0, latency_ms=0, error=None):
    ts = now_iso()
    conn = db()
    try:
        conn.execute(
            """INSERT INTO messages
               (session_id, turn_idx, speaker, model, role, content, raw,
                tokens_in, tokens_out, latency_ms, error, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (session_id, turn_idx, speaker, model, role, content,
             json.dumps(raw) if raw is not None else None,
             tokens_in, tokens_out, latency_ms, error, ts),
        )
        conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (ts, session_id))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
class BackendError(Exception):
    pass


def _post_oai(url, body, auth, timeout):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": auth},
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = str(e)
        raise BackendError(f"HTTP {e.code}: {err_body[:500]}") from e
    except Exception as e:
        raise BackendError(f"network error: {e}") from e
    latency = int((time.monotonic() - t0) * 1000)
    return data, latency


def _extract_text(oai_choice_msg):
    """OpenAI choice message -> flat text. Reasoning models may surface thinking
    in `reasoning` (OpenRouter) or `reasoning_content` (LM Studio / vLLM)."""
    content = oai_choice_msg.get("content") or ""
    reasoning = (oai_choice_msg.get("reasoning")
                 or oai_choice_msg.get("reasoning_content") or "")
    if reasoning and not content:
        return f"<thinking>\n{reasoning}\n</thinking>"
    if reasoning:
        return f"<thinking>\n{reasoning}\n</thinking>\n\n{content}"
    return content


_lmstudio_lock = threading.Lock()  # LM Studio is single-instance; serialize calls.

# ---------------------------------------------------------------------------
# Prompt cleaning â€” normalize messages before sending to any backend.
# Applied automatically to all LM Studio (Gemma/Qwen) calls.
# ---------------------------------------------------------------------------
# Rough chars-per-token estimate for budget enforcement (conservative).
_CHARS_PER_TOKEN = 4
# Default token budget for local models before truncation kicks in.
_LOCAL_TOKEN_BUDGET = int(os.environ.get("LOCAL_PROMPT_TOKENS", "32000"))


def clean_messages(messages, max_tokens=None):
    """Normalize and optionally truncate a message list.

    Steps:
      1. Stringify content (handles multi-part Anthropic blocks).
      2. Strip leading/trailing whitespace per message.
      3. Merge consecutive messages with the same role.
      4. If max_tokens set, drop middle turns to fit budget while keeping
         system messages and the final user message intact.
    """
    if not messages:
        return messages

    cleaned = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content") or ""
        if isinstance(content, list):
            # Flatten Anthropic multi-part blocks to plain text.
            parts = [
                block.get("text", "").strip()
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            content = "\n".join(parts)
        else:
            content = str(content).strip()

        # Merge consecutive same-role messages to reduce noise.
        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1]["content"] += "\n\n" + content
        else:
            cleaned.append({"role": role, "content": content})

    if max_tokens:
        max_chars = max_tokens * _CHARS_PER_TOKEN
        total = sum(len(m["content"]) for m in cleaned)
        if total > max_chars:
            sys_msgs  = [m for m in cleaned if m["role"] == "system"]
            other     = [m for m in cleaned if m["role"] != "system"]
            last      = other[-1] if other else None
            middle    = other[:-1] if other else []
            sys_chars = sum(len(m["content"]) for m in sys_msgs)
            last_chars = len(last["content"]) if last else 0
            budget    = max_chars - sys_chars - last_chars
            kept = []
            used = 0
            for m in reversed(middle):
                chunk = len(m["content"])
                if used + chunk <= budget:
                    kept.insert(0, m)
                    used += chunk
                else:
                    break  # drop older turns that don't fit
            cleaned = sys_msgs + kept + ([last] if last else [])

    return cleaned


def lmstudio_call(model_id, messages, max_tokens=1024, temperature=1.0):
    messages = clean_messages(messages, max_tokens=_LOCAL_TOKEN_BUDGET)
    body = {"model": model_id, "messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "stream": False}
    with _lmstudio_lock:
        data, latency = _post_oai(LM_STUDIO_URL, body, "Bearer lmstudio", GEMMA_TIMEOUT)
    msg = data["choices"][0].get("message", {})
    usage = data.get("usage", {})
    return {
        "text": _extract_text(msg),
        "raw": data,
        "tokens_in": usage.get("prompt_tokens", 0),
        "tokens_out": usage.get("completion_tokens", 0),
        "latency_ms": latency,
    }


def openrouter_call(model_id, messages, max_tokens=1024, temperature=1.0):
    key = get_openrouter_key()
    if not key:
        raise BackendError("OPENROUTER_API_KEY not set")
    body = {"model": model_id, "messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "stream": False}
    data, latency = _post_oai(OPENROUTER_URL, body, f"Bearer {key}", KIMI_TIMEOUT)
    msg = data["choices"][0].get("message", {})
    usage = data.get("usage", {})
    return {
        "text": _extract_text(msg),
        "raw": data,
        "tokens_in": usage.get("prompt_tokens", 0),
        "tokens_out": usage.get("completion_tokens", 0),
        "latency_ms": latency,
    }


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "120"))
CLAUDE_ALIASES = {"claude", "claude-opus", "claude-opus-4-8", "opus", "anthropic"}


def anthropic_call(model_id, messages, max_tokens=1024, temperature=1.0):
    key = get_anthropic_key()
    if not key:
        raise BackendError("ANTHROPIC_API_KEY not set")
    system = ""
    convo = []
    for m in messages:
        if m["role"] == "system":
            system += (m.get("content") or "") + "\n"
        else:
            convo.append({"role": m["role"], "content": m.get("content") or ""})
    body = {"model": model_id, "max_tokens": max_tokens,
            "temperature": temperature, "messages": convo}
    if system.strip():
        body["system"] = system.strip()
    req = urllib.request.Request(
        ANTHROPIC_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=CLAUDE_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode("utf-8", errors="replace")
        except Exception:
            err = str(e)
        raise BackendError(f"HTTP {e.code}: {err[:500]}") from e
    except Exception as e:
        raise BackendError(f"network error: {e}") from e
    parts = data.get("content") or []
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


BACKENDS = {
    "kimi":  {"backend": "openrouter", "underlying": KIMI_MODEL,
              "call": lambda msgs, **opts: openrouter_call(KIMI_MODEL, msgs, **opts)},
    "gemma": {"backend": "lm-studio",  "underlying": LM_STUDIO_MODEL,
              "call": lambda msgs, **opts: lmstudio_call(LM_STUDIO_MODEL, msgs, **opts)},
    "qwen":  {"backend": "lm-studio",  "underlying": QWEN_MODEL,
              "call": lambda msgs, **opts: lmstudio_call(QWEN_MODEL, msgs, **opts)},
    "claude": {"backend": "anthropic", "underlying": CLAUDE_MODEL,
               "call": lambda msgs, **opts: _claude_response(msgs, **opts)},
}


def _claude_response(msgs, **opts):
    text = anthropic_call(CLAUDE_MODEL, msgs, **opts)
    return {
        "text": text,
        "raw": {"object": "chat.completion", "model": CLAUDE_MODEL,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": text}}]},
        "tokens_in": 0, "tokens_out": 0, "latency_ms": 0,
    }


def select_backend(requested_model):
    name = (requested_model or "kimi").lower()
    if name in KIMI_ALIASES:
        return "kimi"
    if name in QWEN_ALIASES:
        return "qwen"
    if name in CLAUDE_ALIASES:
        return "claude"
    return "gemma"


def call_backend(name, messages, **opts):
    name = (name or "").lower()
    if name in KIMI_ALIASES:
        name = "kimi"
    elif name in QWEN_ALIASES:
        name = "qwen"
    elif name in GEMMA_ALIASES:
        name = "gemma"
    elif name in CLAUDE_ALIASES:
        name = "claude"
    spec = BACKENDS.get(name)
    if not spec:
        raise BackendError(f"unknown model: {name}")
    return spec["call"](messages, **opts)


# ---------------------------------------------------------------------------
# Anthropic <-> OpenAI conversion (kept for /v1/messages compatibility)
# ---------------------------------------------------------------------------
def anthropic_to_openai_messages(body):
    messages = list(body.get("messages") or [])
    system = body.get("system")
    flat = []
    if system:
        if isinstance(system, list):
            sys_text = "".join(b.get("text", "") for b in system if b.get("type") == "text")
        else:
            sys_text = system
        flat.append({"role": "system", "content": sys_text})
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            text = "".join(b.get("text", "") for b in c if b.get("type") == "text")
            flat.append({"role": m["role"], "content": text})
        else:
            flat.append({"role": m["role"], "content": c or ""})
    return flat


def to_anthropic_response(text, model, tokens_in, tokens_out):
    return {
        "id": "msg_proxy_" + secrets.token_hex(4),
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": tokens_in, "output_tokens": tokens_out},
    }


# ---------------------------------------------------------------------------
# Mode orchestrators
# ---------------------------------------------------------------------------
def run_pipeline(session_id, input_text, steps, default_max_tokens, start_turn=0):
    """Execute steps, persisting each turn. Returns (output, error_or_none)."""
    prior = input_text
    error = None
    for i, step in enumerate(steps):
        turn_idx = start_turn + i
        model = step.get("model")
        system = step.get("system") or ""
        max_tokens = step.get("max_tokens") or default_max_tokens
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prior})
        try:
            resp = call_backend(model, msgs, max_tokens=max_tokens)
        except BackendError as e:
            append_message(session_id, turn_idx, model, model, "assistant", "",
                           error=str(e))
            error = {"step": turn_idx, "model": model, "message": str(e), "resumable": True}
            break
        append_message(session_id, turn_idx, model, model, "assistant", resp["text"],
                       raw=resp["raw"], tokens_in=resp["tokens_in"],
                       tokens_out=resp["tokens_out"], latency_ms=resp["latency_ms"])
        prior = resp["text"]
    return prior, error


def _room_messages_for_speaker(transcript, topic, speaker_name, persona, memory_context=""):
    sys_content = (f"You are {speaker_name}. {persona}\nTopic: {topic}\n"
                   "Other participants will be quoted to you with [Name]: prefix. "
                   "Respond in your own voice, briefly, advancing the conversation.")
    if memory_context:
        sys_content = memory_context + "\n\n" + sys_content
    msgs = [{"role": "system", "content": sys_content}]
    for m in transcript:
        if m["speaker"] == speaker_name:
            msgs.append({"role": "assistant", "content": m["content"]})
        else:
            msgs.append({"role": "user", "content": f"[{m['speaker']}]: {m['content']}"})
    if not any(m["role"] == "user" for m in msgs):
        msgs.append({"role": "user", "content": f"Begin. Topic: {topic}"})
    return msgs


def run_room(session_id, topic, participants, turns, max_tokens, start_turn=0, memory_context=""):
    """Round-robin. Returns (transcript_list, error_or_none)."""
    error = None
    for t in range(turns):
        idx = (start_turn + t) % len(participants)
        speaker = participants[idx]
        transcript = get_messages(session_id)
        msgs = _room_messages_for_speaker(
            transcript, topic, speaker["name"], speaker.get("persona", ""), memory_context
        )
        try:
            resp = call_backend(speaker["model"], msgs, max_tokens=max_tokens)
        except BackendError as e:
            append_message(session_id, start_turn + t, speaker["name"],
                           speaker["model"], "assistant", "", error=str(e))
            error = {"turn": start_turn + t, "speaker": speaker["name"],
                     "message": str(e), "resumable": True}
            break
        append_message(session_id, start_turn + t, speaker["name"],
                       speaker["model"], "assistant", resp["text"],
                       raw=resp["raw"], tokens_in=resp["tokens_in"],
                       tokens_out=resp["tokens_out"], latency_ms=resp["latency_ms"])
    return get_messages(session_id), error


def run_debate(session_id, prompt, participants, synthesizer, max_tokens):
    """Phase 1 fan-out + Phase 2 synthesis. Returns (answers, synthesis, error_or_none)."""
    def _one(idx, p):
        msgs = [
            {"role": "system", "content": f"Stance: {p.get('stance','')}"},
            {"role": "user", "content": prompt},
        ]
        try:
            resp = call_backend(p["model"], msgs, max_tokens=max_tokens)
            return idx, p, resp, None
        except BackendError as e:
            return idx, p, None, str(e)

    answers = [None] * len(participants)
    error = None
    with ThreadPoolExecutor(max_workers=max(1, len(participants))) as pool:
        futures = [pool.submit(_one, i, p) for i, p in enumerate(participants)]
        for f in as_completed(futures):
            idx, p, resp, err = f.result()
            speaker = p.get("name") or p["model"]
            if err:
                append_message(session_id, idx, speaker, p["model"],
                               "assistant", "", error=err)
                if not error:
                    error = {"phase": "answer", "model": p["model"], "message": err}
                answers[idx] = {"model": p["model"], "stance": p.get("stance", ""),
                                "text": "", "error": err}
            else:
                append_message(session_id, idx, speaker, p["model"],
                               "assistant", resp["text"],
                               raw=resp["raw"], tokens_in=resp["tokens_in"],
                               tokens_out=resp["tokens_out"],
                               latency_ms=resp["latency_ms"])
                answers[idx] = {"model": p["model"], "stance": p.get("stance", ""),
                                "text": resp["text"]}

    if error:
        return answers, None, error

    synth_prompt = f"Prompt: {prompt}\n\n" + "\n".join(
        f"[{(p.get('name') or p['model'])}]: {a['text']}"
        for p, a in zip(participants, answers)
    ) + "\n\nSynthesize."
    msgs = [
        {"role": "system", "content": synthesizer.get("instruction", "Synthesize.")},
        {"role": "user", "content": synth_prompt},
    ]
    try:
        resp = call_backend(synthesizer["model"], msgs, max_tokens=max_tokens)
    except BackendError as e:
        append_message(session_id, len(participants), "synth",
                       synthesizer["model"], "assistant", "", error=str(e))
        return answers, None, {"phase": "synth", "model": synthesizer["model"],
                               "message": str(e)}
    append_message(session_id, len(participants), "synth",
                   synthesizer["model"], "assistant", resp["text"],
                   raw=resp["raw"], tokens_in=resp["tokens_in"],
                   tokens_out=resp["tokens_out"], latency_ms=resp["latency_ms"])
    synthesis = {"model": synthesizer["model"], "text": resp["text"]}
    return answers, synthesis, None


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------
class ProxyHandler(http.server.BaseHTTPRequestHandler):
    server_version = "GloryProxy/2.0"

    def log_message(self, fmt, *args):
        safe_print(f"[proxy] {fmt % args}")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type,Authorization,X-Api-Key,Anthropic-Version")

    def _send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, kind, message, **extra):
        payload = {"error": {"kind": kind, "message": message}}
        payload["error"].update(extra)
        self._send_json(code, payload)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _handle_research(self):
        import html.parser as _hp
        import urllib.request as _ur
        import urllib.parse as _up

        body = self._read_json()
        target_url = (body.get("url") or "").strip()
        if not target_url:
            return self._err(400, "bad_request", "url required")
        if not target_url.startswith("http"):
            target_url = "https://" + target_url

        # SSRF protection â€” block private/loopback targets
        try:
            import ipaddress as _ipa
            _parsed_check = urllib.parse.urlparse(target_url)
            if _parsed_check.scheme not in ('http', 'https'):
                return self._err(400, "bad_request", "only http/https allowed")
            _host = _parsed_check.hostname or ''
            if _host.lower() in ('localhost', ''):
                return self._err(400, "bad_request", "localhost not allowed")
            try:
                _addr = _ipa.ip_address(_host)
                if _addr.is_private or _addr.is_loopback or _addr.is_link_local or _addr.is_reserved:
                    return self._err(400, "bad_request", f"private/reserved IP blocked: {_addr}")
            except ValueError:
                pass  # hostname â€” fine
        except Exception as _ssrf_err:
            return self._err(400, "bad_request", str(_ssrf_err))

        parsed = _up.urlparse(target_url)
        domain = parsed.netloc.replace("www.", "")

        class _Parser(_hp.HTMLParser):
            def __init__(self):
                super().__init__()
                self.title = ""
                self.description = ""
                self.links = []
                self.scripts = []
                self.stylesheets = []
                self._in_title = False

            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag == "title":
                    self._in_title = True
                elif tag == "meta":
                    if a.get("name", "").lower() == "description":
                        self.description = a.get("content", "")
                elif tag == "a":
                    href = a.get("href", "")
                    if href and not href.startswith(("#", "mailto:", "tel:")):
                        self.links.append(href)
                elif tag == "script":
                    src = a.get("src", "")
                    if src:
                        self.scripts.append(src)
                elif tag == "link":
                    if "stylesheet" in a.get("rel", ""):
                        self.stylesheets.append(a.get("href", ""))

            def handle_data(self, data):
                if self._in_title:
                    self.title += data

            def handle_endtag(self, tag):
                if tag == "title":
                    self._in_title = False

        try:
            req = _ur.Request(target_url, headers={"User-Agent": "GloryResearch/1.0"})
            with _ur.urlopen(req, timeout=15) as resp:
                status_code = resp.status
                headers = dict(resp.headers)
                html_bytes = resp.read(500_000)
                html_text = html_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            return self._err(502, "fetch_error", str(e))

        parser = _Parser()
        try:
            parser.feed(html_text)
        except Exception:
            pass

        server = headers.get("Server", headers.get("server", ""))
        powered = headers.get("X-Powered-By", headers.get("x-powered-by", ""))

        tech_patterns = {
            "React": [r"react(?:\.min)?\.js", r"react-dom", r"_reactRoot"],
            "Next.js": [r"/_next/", r"__NEXT_DATA__"],
            "Vue": [r"vue(?:\.min)?\.js", r"vue-router"],
            "Nuxt": [r"_nuxt/"],
            "Angular": [r"angular(?:\.min)?\.js", r"ng-version"],
            "Webpack": [r"webpack", r"__webpack"],
            "Vite": [r"/assets/.*\.js\?", r"vite"],
            "GA4": [r"gtag\(", r"google-analytics\.com", r"googletagmanager\.com"],
            "Segment": [r"analytics\.js", r"segment\.com"],
            "Mixpanel": [r"mixpanel"],
            "Tailwind": [r"tailwind"],
            "Bootstrap": [r"bootstrap(?:\.min)?\.css"],
            "jQuery": [r"jquery(?:\.min)?\.js"],
            "Cloudflare": ["cloudflare"],
            "nginx": ["nginx"],
            "Apache": ["Apache"],
            "Express": ["Express"],
        }

        tech_stack = []
        combined = html_text[:100_000] + " ".join(parser.scripts) + server + powered
        for tech, patterns in tech_patterns.items():
            for pat in patterns:
                if re.search(pat, combined, re.IGNORECASE):
                    if tech not in tech_stack:
                        tech_stack.append(tech)
                    break

        api_re = re.compile(r'["\'](/(?:api|graphql|v\d+|rest|rpc|gql|query)[^"\'?\s]{0,80})', re.IGNORECASE)
        api_patterns_found = list(dict.fromkeys(m.group(1) for m in api_re.finditer(html_text)))[:30]

        base = target_url.rstrip("/")
        internal_links, external_links = [], []
        for lnk in dict.fromkeys(parser.links):
            if lnk.startswith("/"):
                internal_links.append(lnk)
            elif domain in lnk:
                internal_links.append(lnk)
            elif lnk.startswith("http"):
                external_links.append(lnk)
        internal_links = internal_links[:60]
        external_links = external_links[:40]

        assets = ([{"url": s, "type": "script"} for s in parser.scripts[:20]] +
                  [{"url": s, "type": "stylesheet"} for s in parser.stylesheets[:10]])

        date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        safe_domain = re.sub(r"[^\w-]", "-", domain)
        obsidian_dir = os.path.join(os.path.dirname(__file__), "..", "..", "Glory's Intellect", "05 - Research")
        obsidian_dir = os.path.normpath(obsidian_dir)
        obsidian_filename = f"{date_str}-{safe_domain}.md"
        obsidian_path = os.path.join(obsidian_dir, obsidian_filename)

        tech_inline = " Â· ".join(tech_stack) if tech_stack else "Unknown"
        md_lines = [
            f"---",
            f"url: {target_url}",
            f"domain: {domain}",
            f"date: {date_str}",
            f"status: {status_code}",
            f"server: {server or 'unknown'}",
            f"tech_stack: [{', '.join(tech_stack)}]",
            f"---",
            f"",
            f"# Research: {domain}",
            f"",
            f"**Scraped:** {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC  ",
            f"**Status:** {status_code}  ",
            f"**Server:** {server or 'unknown'}  ",
            f"**Tech Stack:** {tech_inline}",
            f"",
        ]
        if api_patterns_found:
            md_lines += [f"## API Endpoints", ""] + [f"- {p}" for p in api_patterns_found] + [""]
        if assets:
            md_lines += [f"## Assets ({len(assets)})", ""] + [f"- {a['url']} ({a['type']})" for a in assets[:15]] + [""]
        if internal_links:
            md_lines += [f"## Internal Links ({len(internal_links)})", ""] + [f"- {l}" for l in internal_links[:20]] + [""]
        if external_links:
            md_lines += [f"## External Links ({len(external_links)})", ""] + [f"- {l}" for l in external_links[:15]] + [""]
        if parser.description:
            md_lines += [f"## Description", "", parser.description, ""]

        saved = False
        try:
            os.makedirs(obsidian_dir, exist_ok=True)
            with open(obsidian_path, "w", encoding="utf-8") as f:
                f.write("\n".join(md_lines))
            saved = True
        except Exception:
            pass

        entry_id = str(uuid.uuid4())
        conn = db()
        try:
            conn.execute(
                "INSERT INTO research_log(id, url, domain, status, tech_stack, api_patterns, obsidian_path) VALUES (?,?,?,?,?,?,?)",
                (entry_id, target_url, domain, status_code,
                 json.dumps(tech_stack), json.dumps(api_patterns_found),
                 obsidian_path if saved else None)
            )
            conn.commit()
        finally:
            conn.close()

        self._send_json(200, {
            "url": target_url,
            "domain": domain,
            "status": status_code,
            "server": server,
            "title": parser.title.strip(),
            "description": parser.description,
            "tech_stack": tech_stack,
            "links": {"internal": internal_links, "external": external_links},
            "assets": assets,
            "api_patterns": api_patterns_found,
            "obsidian_path": obsidian_path if saved else None,
            "saved": saved,
        })

    def _handle_tasks_list(self):
        conn = db()
        try:
            rows = conn.execute(
                "SELECT id, name, prompt, schedule, enabled, last_run, last_result, run_count, created_at "
                "FROM glory_tasks ORDER BY created_at DESC"
            ).fetchall()
            tasks = [dict(r) for r in rows]
            return self._send_json(200, {"tasks": tasks})
        finally:
            conn.close()

    def _handle_task_create(self):
        body = self._read_json()
        name = (body.get("name") or "").strip()
        prompt = (body.get("prompt") or "").strip()
        if not name or not prompt:
            return self._err(400, "bad_request", "name and prompt required")
        tid = str(uuid.uuid4())
        conn = db()
        try:
            conn.execute(
                "INSERT INTO glory_tasks(id, name, prompt, schedule, enabled) VALUES (?,?,?,?,?)",
                (tid, name, prompt, body.get("schedule") or None, 1)
            )
            conn.commit()
        finally:
            conn.close()
        return self._send_json(200, {"ok": True, "id": tid})

    def _handle_task_run(self, tid):
        conn = db()
        try:
            row = conn.execute("SELECT * FROM glory_tasks WHERE id=?", (tid,)).fetchone()
            if not row:
                return self._err(404, "not_found", "task not found")
            prompt = row["prompt"]
        finally:
            conn.close()
        try:
            msgs = [{"role": "user", "content": prompt}]
            result_text, _ = lmstudio_call(LM_STUDIO_MODEL, msgs, timeout=60)
        except Exception as e:
            result_text = f"Error: {e}"
        ts = now_iso()
        conn = db()
        try:
            conn.execute(
                "UPDATE glory_tasks SET last_run=?, last_result=?, run_count=run_count+1 WHERE id=?",
                (ts, str(result_text)[:500], tid)
            )
            conn.commit()
        finally:
            conn.close()
        return self._send_json(200, {"ok": True, "result": result_text, "ran_at": ts})

    def _handle_task_delete(self, tid):
        conn = db()
        try:
            conn.execute("DELETE FROM glory_tasks WHERE id=?", (tid,))
            conn.commit()
        finally:
            conn.close()
        return self._send_json(200, {"ok": True})

    def _handle_agent_bus_get(self):
        limit = 50
        conn = db()
        try:
            rows = conn.execute(
                "SELECT id, from_agent, to_agent, content, thread, created_at "
                "FROM agent_messages ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            msgs = [dict(r) for r in reversed(rows)]
            return self._send_json(200, {"messages": msgs})
        finally:
            conn.close()

    def _handle_agent_bus_post(self):
        body = self._read_json()
        from_agent = (body.get("from_agent") or "unknown").strip()
        to_agent = (body.get("to_agent") or "all").strip()
        content = (body.get("content") or "").strip()
        if not content:
            return self._err(400, "bad_request", "content required")
        thread = body.get("thread") or None
        conn = db()
        try:
            conn.execute(
                "INSERT INTO agent_messages(from_agent, to_agent, content, thread) VALUES (?,?,?,?)",
                (from_agent, to_agent, content[:2000], thread)
            )
            conn.commit()
        finally:
            conn.close()
        return self._send_json(200, {"ok": True})

    def _handle_glory_agents(self):
        def _port_up(port, host='127.0.0.1'):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.4)
                r = s.connect_ex((host, port))
                s.close()
                return r == 0
            except Exception:
                return False

        lm_studio_up = _port_up(1234, LM_STUDIO_HOST)
        hermes_up = _port_up(8083)

        kimi_recent = False
        try:
            conn = db()
            cutoff = (datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S')
            row = conn.execute(
                "SELECT 1 FROM messages WHERE model LIKE '%kimi%' AND created_at > ? LIMIT 1",
                (cutoff,)
            ).fetchone()
            conn.close()
            kimi_recent = row is not None
        except Exception:
            pass

        swarm_id, swarm_status = None, 'offline'
        try:
            swarm_path = os.path.normpath(os.path.join(
                os.path.dirname(__file__), '..', '..', '.swarm', 'state.json'
            ))
            if os.path.exists(swarm_path):
                with open(swarm_path) as f:
                    sw = json.load(f)
                swarm_id = sw.get('id')
                swarm_status = sw.get('status', 'ready')
        except Exception:
            pass

        agents = [
            {'id': 'claude',  'name': 'Claude',  'role': 'head', 'color': '#57ff3b',
             'status': 'orchestrating', 'backend': 'anthropic',   'description': 'Primary orchestrator â€” Glory OS HEAD'},
            {'id': 'gemma',   'name': 'Gemma',   'role': 'body', 'color': '#22c4a1',
             'status': 'active' if lm_studio_up else 'offline',   'backend': 'lm-studio',   'description': 'Local vision model'},
            {'id': 'qwen',    'name': 'Qwen',    'role': 'body', 'color': '#ffb347',
             'status': 'active' if lm_studio_up else 'offline',   'backend': 'lm-studio',   'description': 'Local reasoning model'},
            {'id': 'kimi',    'name': 'Kimi',    'role': 'body', 'color': '#87ceeb',
             'status': 'active' if kimi_recent else 'idle',        'backend': 'openrouter',  'description': 'Cloud frontier model'},
            {'id': 'hermes',  'name': 'Hermes',  'role': 'body', 'color': '#c280ff',
             'status': 'active' if hermes_up else 'idle',          'backend': 'local',       'description': 'Local messenger agent'},
        ]
        self._send_json(200, {'agents': agents, 'swarm_id': swarm_id, 'swarm_status': swarm_status})

    def _handle_ports(self):
        ports_list = [
            ("127.0.0.1", 8082, "glory-proxy"),
            ("127.0.0.1", 5173, "vite-ui"),
            (LM_STUDIO_HOST, 1234, "lm-studio"),
            ("127.0.0.1", 11434, "ollama"),
            ("127.0.0.1", 8083, "hermes"),
            ("127.0.0.1", 8080, "generic-http"),
        ]
        results = []
        for host, port, service in ports_list:
            t0 = time.time()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            err = s.connect_ex((host, port))
            s.close()
            latency = round((time.time() - t0) * 1000) if err == 0 else None
            results.append({"port": port, "service": service,
                             "status": "online" if err == 0 else "offline",
                             "latency_ms": latency})
        self._send_json(200, {"ports": results})

    def _handle_schedules(self):
        entries = []
        conn = db()
        try:
            rows = conn.execute(
                "SELECT id, title, cron, description, created_at FROM manual_schedules ORDER BY created_at DESC"
            ).fetchall()
            for r in rows:
                entries.append({"id": r["id"], "source": "manual", "title": r["title"],
                                 "cron": r["cron"], "description": r["description"],
                                 "created_at": r["created_at"]})
        finally:
            conn.close()
        try:
            result = subprocess.run(
                ["claude", "crons", "--output-format", "json"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                cc_entries = json.loads(result.stdout or "[]")
                for e in (cc_entries if isinstance(cc_entries, list) else []):
                    entries.append({"id": e.get("id", str(uuid.uuid4())),
                                    "source": "claude-code",
                                    "title": e.get("name", e.get("prompt", "")[:60]),
                                    "cron": e.get("schedule"),
                                    "description": e.get("prompt"),
                                    "created_at": None})
        except Exception:
            pass
        try:
            req = urllib.request.Request("http://127.0.0.1:8083/schedules")
            with urllib.request.urlopen(req, timeout=3) as resp:
                hermes_data = json.loads(resp.read())
                for e in (hermes_data if isinstance(hermes_data, list) else hermes_data.get("schedules", [])):
                    entries.append({"id": e.get("id", str(uuid.uuid4())),
                                    "source": "hermes",
                                    "title": e.get("title", e.get("name", "")),
                                    "cron": e.get("cron"),
                                    "description": e.get("description"),
                                    "created_at": e.get("created_at")})
        except Exception:
            pass
        self._send_json(200, {"schedules": entries})

    def _handle_schedule_add(self):
        body = self._read_json()
        title = body.get("title", "").strip()
        if not title:
            return self._err(400, "bad_request", "title required")
        entry_id = str(uuid.uuid4())
        cron = body.get("cron") or None
        desc = body.get("description") or None
        conn = db()
        try:
            conn.execute(
                "INSERT INTO manual_schedules(id, title, cron, description) VALUES (?,?,?,?)",
                (entry_id, title, cron, desc)
            )
            conn.commit()
        finally:
            conn.close()
        self._send_json(200, {"ok": True, "id": entry_id})

    def _handle_schedule_del(self, entry_id):
        conn = db()
        try:
            conn.execute("DELETE FROM manual_schedules WHERE id=?", (entry_id,))
            conn.commit()
        finally:
            conn.close()
        self._send_json(200, {"ok": True})

    def _handle_network(self):
        import socket as _sock
        local_ip = _sock.gethostbyname(_sock.gethostname())
        devices = [{"ip": local_ip, "mac": "local", "type": "static"}]
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
            pattern = re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+([\w:.-]+)\s+(\S+)')
            for line in result.stdout.splitlines():
                m = pattern.search(line)
                if not m:
                    continue
                mac = m.group(2)
                dtype = m.group(3)
                if mac == "---" or dtype.startswith("0x"):
                    continue
                devices.append({"ip": m.group(1), "mac": mac, "type": dtype})
        except Exception:
            pass
        self._send_json(200, {"devices": devices})


    # ------------------------------------------------------------------
    # /v1/scout  -- full site intelligence (two-phase: scrape + AI)
    # ------------------------------------------------------------------
    def _handle_scout(self):
        import html.parser as _hp
        import urllib.request as _ur
        import urllib.parse as _up
        import ipaddress as _ipa

        body = self._read_json()
        target_url = (body.get("url") or "").strip()
        if not target_url:
            return self._err(400, "bad_request", "url required")
        if not target_url.startswith("http"):
            target_url = "https://" + target_url

        _parsed_check = _up.urlparse(target_url)
        if _parsed_check.scheme not in ("http", "https"):
            return self._err(400, "bad_request", "only http/https allowed")
        _host = _parsed_check.hostname or ""
        if _host.lower() in ("localhost", ""):
            return self._err(400, "bad_request", "localhost not allowed")
        try:
            _addr = _ipa.ip_address(_host)
            if _addr.is_private or _addr.is_loopback or _addr.is_link_local or _addr.is_reserved:
                return self._err(400, "bad_request", f"private/reserved IP blocked: {_addr}")
        except ValueError:
            pass

        parsed_url = _up.urlparse(target_url)
        base = f"{parsed_url.scheme}://{parsed_url.netloc}"
        domain = parsed_url.netloc.replace("www.", "")

        class _Parser(_hp.HTMLParser):
            def __init__(self):
                super().__init__()
                self.title = ""
                self.description = ""
                self.og = {}
                self.links = []
                self.scripts = []
                self.stylesheets = []
                self.forms = []
                self._in_title = False
                self._cur_form = None

            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag == "title":
                    self._in_title = True
                elif tag == "meta":
                    name = a.get("name", a.get("property", "")).lower()
                    content = a.get("content", "")
                    if name == "description":
                        self.description = content
                    elif name.startswith("og:"):
                        self.og[name[3:]] = content
                elif tag == "a":
                    href = a.get("href", "")
                    if href and not href.startswith(("#", "mailto:", "tel:")):
                        self.links.append(href)
                elif tag == "script":
                    src = a.get("src", "")
                    if src:
                        self.scripts.append(src)
                elif tag == "link":
                    if "stylesheet" in a.get("rel", ""):
                        self.stylesheets.append(a.get("href", ""))
                elif tag == "form":
                    self._cur_form = {"action": a.get("action", ""), "method": a.get("method", "get"), "inputs": []}
                    self.forms.append(self._cur_form)
                elif tag == "input":
                    if self._cur_form is not None:
                        self._cur_form["inputs"].append({"type": a.get("type", "text"), "name": a.get("name", "")})

            def handle_data(self, data):
                if self._in_title:
                    self.title += data

            def handle_endtag(self, tag):
                if tag == "title":
                    self._in_title = False
                elif tag == "form":
                    self._cur_form = None

        def _fetch(url, timeout=10):
            try:
                req = _ur.Request(url, headers={"User-Agent": "GloryScout/1.0"})
                with _ur.urlopen(req, timeout=timeout) as r:
                    return r.status, dict(r.headers), r.read(500_000).decode("utf-8", errors="replace")
            except Exception as e:
                return None, {}, str(e)

        def _probe(path):
            url = base.rstrip("/") + path
            try:
                req = _ur.Request(url, headers={"User-Agent": "GloryScout/1.0"})
                with _ur.urlopen(req, timeout=6) as r:
                    return {"path": path, "status": r.status,
                            "content_type": r.headers.get("Content-Type", ""), "size": len(r.read(4096))}
            except _ur.HTTPError as e:
                return {"path": path, "status": e.code, "content_type": "", "size": 0}
            except Exception:
                return {"path": path, "status": None, "content_type": "", "size": 0}

        status_code, headers, html_text = _fetch(target_url, timeout=15)
        if status_code is None:
            return self._err(502, "fetch_error", html_text)

        robots_status, _, robots_body = _fetch(base + "/robots.txt", timeout=8)
        sitemap_status, _, sitemap_body = _fetch(base + "/sitemap.xml", timeout=8)

        probe_paths = [
            "/api", "/api/v1", "/graphql", "/.well-known/security.txt",
            "/admin", "/login", "/wp-login.php", "/health", "/status",
            "/metrics", "/swagger.json", "/openapi.json", "/.env", "/.git/config",
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            probe_futures = [pool.submit(_probe, p) for p in probe_paths]
            probe_results = sorted([f.result() for f in as_completed(probe_futures)], key=lambda x: x["path"])

        parser = _Parser()
        try:
            parser.feed(html_text)
        except Exception:
            pass

        tech_patterns = {
            "React": [r"react(?:\.min)?\.js", r"react-dom", r"_reactRoot"],
            "Next.js": [r"/_next/", r"__NEXT_DATA__"],
            "Vue": [r"vue(?:\.min)?\.js", r"vue-router"],
            "Nuxt": [r"_nuxt/"],
            "Angular": [r"angular(?:\.min)?\.js", r"ng-version"],
            "Svelte": [r"svelte"],
            "Webpack": [r"webpack", r"__webpack"],
            "Vite": [r"/assets/.*\.js\?", r"\bvite\b"],
            "GraphQL": [r"graphql", r"__schema"],
            "GA4/GTM": [r"gtag\(", r"googletagmanager\.com"],
            "Tailwind": [r"tailwind"],
            "Bootstrap": [r"bootstrap(?:\.min)?\.css"],
            "jQuery": [r"jquery(?:\.min)?\.js"],
            "Cloudflare": [r"cloudflare"],
            "nginx": [r"nginx"],
            "Apache": [r"Apache"],
            "WordPress": [r"wp-content", r"wp-includes"],
            "Shopify": [r"shopify"],
            "Stripe": [r"js\.stripe\.com"],
            "Vercel": [r"vercel\.app", r"_vercel"],
            "Firebase": [r"firebase", r"firebaseapp\.com"],
        }
        server = headers.get("Server", headers.get("server", ""))
        powered = headers.get("X-Powered-By", headers.get("x-powered-by", ""))
        combined = html_text[:150_000] + " ".join(parser.scripts) + server + powered
        tech_stack = []
        for tech, pats in tech_patterns.items():
            for pat in pats:
                if re.search(pat, combined, re.IGNORECASE):
                    tech_stack.append(tech)
                    break

        sec_header_names = [
            "Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options",
            "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy",
            "X-XSS-Protection", "Cross-Origin-Opener-Policy",
        ]
        headers_lower = {k.lower(): v for k, v in headers.items()}
        security_audit = []
        for hdr in sec_header_names:
            present = hdr.lower() in headers_lower
            security_audit.append({
                "header": hdr, "present": present,
                "value": headers_lower.get(hdr.lower()),
                "risk": "low" if present else "high",
            })
        security_score = sum(1 for s in security_audit if s["present"])

        set_cookie_hdr = headers_lower.get("set-cookie", "")
        cookies_info = []
        for ck in (set_cookie_hdr.split(",\n") if set_cookie_hdr else []):
            ck = ck.strip()
            if not ck:
                continue
            parts = [p.strip() for p in ck.split(";")]
            flags = [p.lower() for p in parts[1:]]
            cookies_info.append({
                "raw": parts[0],
                "httponly": "httponly" in flags,
                "secure": "secure" in flags,
                "samesite": next((p for p in flags if p.startswith("samesite")), None),
            })

        api_re = re.compile(r"[\"'](/(?:api|graphql|v\d+|rest|rpc|gql|query)[^\"'?\s]{0,80})", re.IGNORECASE)
        api_patterns_found = list(dict.fromkeys(m.group(1) for m in api_re.finditer(html_text)))[:40]

        secret_patterns = {
            "API Key": r"(?:api[_-]?key|apikey)\s*[:=]\s*[\"']([A-Za-z0-9_\-]{16,})[\"']",
            "AWS Access Key": r"AKIA[0-9A-Z]{16}",
            "JWT": r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
            "Google API Key": r"AIza[0-9A-Za-z_\-]{35}",
            "Stripe Key": r"(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{24,}",
            "Basic Auth URL": r"https?://[^:@\s]+:[^@\s]+@[^\s/\"]+",
        }
        secrets_found = []
        for label, pat in secret_patterns.items():
            matches = re.findall(pat, html_text[:300_000])
            if matches:
                secrets_found.append({"type": label, "count": len(matches), "sample": str(matches[0])[:80]})

        internal_links, external_links = [], []
        for lnk in dict.fromkeys(parser.links):
            if lnk.startswith("/") or domain in lnk:
                internal_links.append(lnk)
            elif lnk.startswith("http"):
                external_links.append(lnk)

        robots_disallowed = []
        if robots_status == 200:
            for line in robots_body.splitlines():
                if line.strip().lower().startswith("disallow:"):
                    pv = line.split(":", 1)[1].strip()
                    if pv:
                        robots_disallowed.append(pv)

        sitemap_urls = []
        if sitemap_status == 200:
            sitemap_urls = re.findall(r"<loc>(https?://[^<]+)</loc>", sitemap_body)[:30]

        phase1 = {
            "url": target_url, "domain": domain, "status": status_code,
            "server": server, "powered_by": powered,
            "title": parser.title.strip(), "description": parser.description, "og": parser.og,
            "tech_stack": tech_stack,
            "security_audit": security_audit,
            "security_score": f"{security_score}/{len(sec_header_names)}",
            "all_headers": dict(headers),
            "cookies": cookies_info,
            "api_patterns": api_patterns_found,
            "secrets_found": secrets_found,
            "forms": parser.forms[:10],
            "assets": ([{"url": s, "type": "script"} for s in parser.scripts[:20]] +
                       [{"url": s, "type": "stylesheet"} for s in parser.stylesheets[:10]]),
            "links": {"internal": internal_links[:60], "external": external_links[:40]},
            "probe_results": probe_results,
            "robots": {"status": robots_status, "disallowed": robots_disallowed[:30]},
            "sitemap": {"status": sitemap_status, "urls": sitemap_urls},
        }

        ai_summary = None
        ai_error = None
        try:
            missing_hdrs = ", ".join(s["header"] for s in security_audit if not s["present"])
            probe_hits = ", ".join(
                f"{p['path']}={p['status']}" for p in probe_results
                if p["status"] and p["status"] not in (404, 403, None)
            )
            summary_prompt = f"""You are a security and backend architecture analyst. Analyze site intelligence for {domain} and provide a concise report with these exact sections:

1. Backend Architecture - What stack/infra is likely running this?
2. Security Posture - Key risks; score is {phase1['security_score']} security headers present
3. API Surface - Exposed endpoints and what they suggest
4. Secrets Risk - Credentials/tokens found in source
5. Notable Findings - Anything unusual

Be direct, technical, 2-3 sentences per section.

Data:
- Tech: {', '.join(tech_stack) or 'unknown'}
- Server: {server or 'unknown'} | Powered-by: {powered or 'unknown'}
- Missing headers: {missing_hdrs or 'none'}
- API paths: {', '.join(api_patterns_found[:10]) or 'none'}
- Secrets: {', '.join(s['type'] for s in secrets_found) or 'none'}
- Probe hits: {probe_hits or 'none'}
- Robots disallowed: {', '.join(robots_disallowed[:8]) or 'none'}
- Forms: {len(parser.forms)} | Cookies: {len(cookies_info)} ({sum(1 for c in cookies_info if not c['httponly'])} no HttpOnly)
"""
            gemma_resp = call_backend("gemma", [{"role": "user", "content": summary_prompt}],
                                      max_tokens=700, temperature=0.3)
            ai_summary = gemma_resp["text"]
        except Exception as e:
            ai_error = str(e)

        self._send_json(200, {**phase1, "ai_summary": ai_summary, "ai_error": ai_error})

    def do_GET(self):
        try:
            if self.path == "/v1/models":
                return self._handle_models()
            if self.path == "/v1/sessions":
                return self._send_json(200, {"sessions": list_sessions()})
            if self.path.startswith("/v1/sessions/"):
                sid = self.path[len("/v1/sessions/"):].split("?")[0]
                return self._handle_get_session(sid)
            if self.path == "/v1/memory":
                return self._send_json(200, {"entries": list_memory()})
            if self.path == "/v1/stats":
                return self._send_json(200, get_stats())
            if self.path == "/" or self.path == "/health":
                return self._send_json(200, {"status": "ok",
                                             "modes_enabled": GLORY_MODES_ENABLED})
            if self.path == "/v1/ports":
                return self._handle_ports()
            if self.path == "/v1/schedules":
                return self._handle_schedules()
            if self.path == "/v1/network":
                return self._handle_network()
            if self.path == '/v1/glory-agents':
                return self._handle_glory_agents()
            if self.path == '/v1/tasks':
                return self._handle_tasks_list()
            if self.path == '/v1/agent-bus':
                return self._handle_agent_bus_get()
            return self._err(404, "not_found", f"GET {self.path}")
        except Exception:
            tb = traceback.format_exc()
            safe_print(f"[proxy] UNHANDLED:\n{tb}")
            try:
                self._err(500, "internal", tb)
            except Exception:
                pass

    def do_POST(self):
        try:
            if self.path == "/v1/messages":
                return self._handle_messages()
            if self.path == "/v1/chat/completions":
                return self._handle_chat_completions()
            if self.path == "/v1/memory":
                return self._handle_memory_upsert()
            if not GLORY_MODES_ENABLED:
                return self._err(404, "not_found", "modes disabled")
            if self.path == "/v1/pipeline":
                return self._handle_pipeline()
            if self.path == "/v1/room":
                return self._handle_room()
            if self.path == "/v1/debate":
                return self._handle_debate()
            if self.path == "/v1/glory":
                return self._handle_glory()
            if self.path.startswith("/v1/sessions/") and self.path.endswith("/continue"):
                sid = self.path[len("/v1/sessions/"):-len("/continue")]
                return self._handle_continue(sid)
            if self.path == "/v1/schedules":
                return self._handle_schedule_add()
            if self.path == "/v1/research":
                return self._handle_research()
            if self.path == "/v1/tasks":
                return self._handle_task_create()
            if self.path.startswith("/v1/tasks/") and self.path.endswith("/run"):
                tid = self.path[len("/v1/tasks/"):-len("/run")]
                return self._handle_task_run(tid)
            if self.path == "/v1/agent-bus":
                return self._handle_agent_bus_post()
            if self.path == "/v1/scout":
                return self._handle_scout()
            return self._err(404, "not_found", f"POST {self.path}")
        except json.JSONDecodeError as e:
            self._err(400, "bad_request", f"invalid JSON: {e}")
        except Exception:
            tb = traceback.format_exc()
            safe_print(f"[proxy] UNHANDLED:\n{tb}")
            try:
                self._err(500, "internal", tb)
            except Exception:
                pass

    def _handle_models(self):
        models = [{"id": k, "backend": v["backend"], "underlying": v["underlying"]}
                  for k, v in BACKENDS.items()]
        self._send_json(200, {"models": models})

    def _handle_messages(self):
        body = self._read_json()
        requested_model = (body.get("model") or "gemma").lower()
        backend_name = select_backend(requested_model)
        msgs = anthropic_to_openai_messages(body)
        max_tokens = body.get("max_tokens", 4096)
        try:
            resp = call_backend(backend_name, msgs, max_tokens=max_tokens,
                                temperature=body.get("temperature", 1.0))
        except BackendError as e:
            return self._err(502, "backend", str(e))
        self._send_json(200, to_anthropic_response(
            resp["text"], requested_model, resp["tokens_in"], resp["tokens_out"]
        ))

    def _handle_chat_completions(self):
        body = self._read_json()
        requested_model = (body.get("model") or "kimi").lower()
        backend_name = select_backend(requested_model)
        msgs = body.get("messages") or []
        if not msgs:
            return self._err(400, "bad_request", "messages required")
        opts = {}
        if "max_tokens" in body:
            opts["max_tokens"] = body["max_tokens"]
        if "temperature" in body:
            opts["temperature"] = body["temperature"]
        try:
            resp = call_backend(backend_name, msgs, **opts)
        except BackendError as e:
            return self._err(502, "backend", str(e))
        # Merge reasoning into content so OpenAI-SDK clients (like Hermes)
        # see the full response â€” reasoning models leave content empty
        # and surface thinking in `reasoning` / `reasoning_content`.
        raw = resp["raw"]
        try:
            raw["choices"][0]["message"]["content"] = resp["text"]
        except (KeyError, IndexError, TypeError):
            pass
        self._send_json(200, raw)

    def _handle_pipeline(self):
        body = self._read_json()
        input_text = body.get("input")
        steps = body.get("steps") or []
        if not input_text or not steps:
            return self._err(400, "bad_request", "input and steps required")
        for s in steps:
            if not s.get("model"):
                return self._err(400, "bad_request", "each step needs model")
        default_max = body.get("max_tokens_per_step", 1024)
        inject_memory = body.get("inject_memory", False)
        if inject_memory:
            mem_ctx = get_memory_context()
            if mem_ctx and steps:
                steps[0]["system"] = mem_ctx + "\n\n" + (steps[0].get("system") or "")
        sid = body.get("session_id")
        if sid:
            sess = get_session(sid)
            if not sess:
                return self._err(404, "not_found", f"session {sid}")
            if sess["mode"] != "pipeline":
                return self._err(400, "bad_request",
                                 f"session is mode={sess['mode']}, not pipeline")
            existing = get_messages(sid)
            start_turn = (max((m["turn_idx"] for m in existing), default=-1)) + 1
        else:
            sid = create_session("pipeline",
                                 {"input": input_text, "steps": steps,
                                  "max_tokens_per_step": default_max})
            start_turn = 0
        with session_lock(sid):
            output, error = run_pipeline(sid, input_text, steps, default_max,
                                         start_turn=start_turn)
        trace = [{"step": m["turn_idx"], "model": m["model"], "text": m["content"]}
                 for m in get_messages(sid)]
        result = {"session_id": sid, "output": output, "trace": trace}
        if error:
            result["error"] = error
            return self._send_json(502, result)
        self._send_json(200, result)

    def _handle_room(self):
        body = self._read_json()
        topic = body.get("topic")
        participants = body.get("participants") or []
        turns = body.get("turns")
        if not topic or not participants or not turns:
            return self._err(400, "bad_request",
                             "topic, participants, turns required")
        for p in participants:
            if not p.get("model") or not p.get("name"):
                return self._err(400, "bad_request",
                                 "each participant needs model and name")
        max_tokens = body.get("max_tokens_per_turn", 512)
        inject_memory = body.get("inject_memory", False)
        sid = body.get("session_id")
        if sid:
            sess = get_session(sid)
            if not sess:
                return self._err(404, "not_found", f"session {sid}")
            if sess["mode"] != "room":
                return self._err(400, "bad_request",
                                 f"session is mode={sess['mode']}, not room")
            participants = sess["meta"]["participants"]
            topic = sess["meta"]["topic"]
            existing = get_messages(sid)
            start_turn = (max((m["turn_idx"] for m in existing), default=-1)) + 1
        else:
            sid = create_session("room", {"topic": topic,
                                          "participants": participants,
                                          "max_tokens_per_turn": max_tokens})
            start_turn = 0
        memory_ctx = get_memory_context() if inject_memory else ""
        with session_lock(sid):
            transcript, error = run_room(sid, topic, participants, turns,
                                         max_tokens, start_turn=start_turn,
                                         memory_context=memory_ctx)
        result = {"session_id": sid,
                  "transcript": [{"turn": m["turn_idx"], "speaker": m["speaker"],
                                  "model": m["model"], "text": m["content"]}
                                 for m in transcript]}
        if error:
            result["error"] = error
            return self._send_json(502, result)
        self._send_json(200, result)

    def _call_hermes_or_fallback(self, prompt, system=None):
        try:
            req_body = json.dumps({"message": prompt, "model": "gemma"}).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:8083/chat",
                data=req_body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return data.get("response", data.get("text", str(data))), None
        except Exception:
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": prompt})
            try:
                result = lmstudio_call(LM_STUDIO_MODEL, msgs)
                return result["text"], result
            except Exception as e:
                return None, str(e)

    def _handle_glory(self):
        body = self._read_json()
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return self._err(400, "bad_request", "prompt required")
        context = body.get("context") or ""
        save_session = body.get("save_session", True)

        t_start = time.monotonic()

        # Phase 1: fan-out to all 3 body models in parallel
        def _call_gemma():
            msgs = []
            if context:
                msgs.append({"role": "system", "content": context})
            msgs.append({"role": "user", "content": prompt})
            try:
                r = lmstudio_call(LM_STUDIO_MODEL, msgs)
                return {"model": "gemma", "role": "leg", "response": r["text"],
                        "latency_ms": r["latency_ms"], "_raw": r}
            except Exception as e:
                return {"model": "gemma", "role": "leg", "response": "",
                        "latency_ms": 0, "error": str(e), "_raw": None}

        def _call_qwen():
            msgs = []
            if context:
                msgs.append({"role": "system", "content": context})
            msgs.append({"role": "user", "content": prompt})
            try:
                r = lmstudio_call(QWEN_MODEL, msgs)
                return {"model": "qwen", "role": "arm", "response": r["text"],
                        "latency_ms": r["latency_ms"], "_raw": r}
            except Exception as e:
                return {"model": "qwen", "role": "arm", "response": "",
                        "latency_ms": 0, "error": str(e), "_raw": None}

        def _call_hermes():
            text, result = self._call_hermes_or_fallback(prompt, system=context or None)
            if text is None:
                return {"model": "hermes", "role": "arm", "response": "",
                        "latency_ms": 0, "error": result, "_raw": None}
            latency = result["latency_ms"] if isinstance(result, dict) else 0
            return {"model": "hermes", "role": "arm", "response": text,
                    "latency_ms": latency, "_raw": result if isinstance(result, dict) else None}

        body_responses = [None, None, None]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(_call_gemma): 0,
                pool.submit(_call_qwen): 1,
                pool.submit(_call_hermes): 2,
            }
            for f in as_completed(futures):
                idx = futures[f]
                try:
                    body_responses[idx] = f.result(timeout=90)
                except Exception as e:
                    names = ["gemma", "qwen", "hermes"]
                    roles = ["leg", "arm", "arm"]
                    body_responses[idx] = {"model": names[idx], "role": roles[idx],
                                           "response": "", "latency_ms": 0,
                                           "error": str(e), "_raw": None}

        total_latency_ms = int((time.monotonic() - t_start) * 1000)

        # Phase 2: synthesis via Kimi (OpenRouter)
        gemma_resp = body_responses[0]
        qwen_resp   = body_responses[1]
        hermes_resp = body_responses[2]

        synthesis_prompt = (
            f'You are Glory â€” a unified AI intelligence. '
            f'The following are responses from your body parts to the question: "{prompt}"\n\n'
            f'GEMMA (leg â€” grounding, vision):\n{gemma_resp["response"] or gemma_resp.get("error", "")}\n\n'
            f'QWEN (arm â€” reasoning, action):\n{qwen_resp["response"] or qwen_resp.get("error", "")}\n\n'
            f'HERMES (arm â€” messaging, execution):\n{hermes_resp["response"] or hermes_resp.get("error", "")}\n\n'
            f'Synthesize these perspectives into one clear, definitive answer. Be concise and decisive.'
        )
        synthesis_messages = [{"role": "user", "content": synthesis_prompt}]
        synthesis_text = ""
        synthesis_error = None
        try:
            synth_r = openrouter_call(KIMI_MODEL, synthesis_messages, max_tokens=2048)
            synthesis_text = synth_r["text"]
        except Exception as e:
            synthesis_error = str(e)
            synthesis_text = ""

        # Phase 3: session persistence
        sid = None
        if save_session:
            sid = create_session("glory", {"prompt": prompt, "context": context})
            for i, br in enumerate(body_responses):
                append_message(
                    sid, i, br["model"], br["model"], "assistant",
                    br["response"],
                    raw=br.get("_raw", {}).get("raw") if br.get("_raw") else None,
                    tokens_in=br.get("_raw", {}).get("tokens_in", 0) if br.get("_raw") else 0,
                    tokens_out=br.get("_raw", {}).get("tokens_out", 0) if br.get("_raw") else 0,
                    latency_ms=br["latency_ms"],
                    error=br.get("error"),
                )
            append_message(
                sid, len(body_responses), "kimi", KIMI_MODEL, "assistant",
                synthesis_text,
                error=synthesis_error,
            )

        # Strip internal _raw field before sending response
        clean_responses = [
            {k: v for k, v in br.items() if k != "_raw"}
            for br in body_responses
        ]

        result = {
            "prompt": prompt,
            "body_responses": clean_responses,
            "synthesis": synthesis_text,
            "session_id": sid,
            "total_latency_ms": total_latency_ms,
        }
        if synthesis_error:
            result["synthesis_error"] = synthesis_error
        self._send_json(200, result)

    def _handle_debate(self):
        body = self._read_json()
        prompt = body.get("prompt")
        participants = body.get("participants") or []
        synthesizer = body.get("synthesizer") or {}
        if not prompt or not participants or not synthesizer.get("model"):
            return self._err(400, "bad_request",
                             "prompt, participants, synthesizer.model required")
        for p in participants:
            if not p.get("model"):
                return self._err(400, "bad_request",
                                 "each participant needs model")
        max_tokens = body.get("max_tokens", 1024)
        sid = create_session("debate", {"prompt": prompt,
                                        "participants": participants,
                                        "synthesizer": synthesizer,
                                        "max_tokens": max_tokens})
        with session_lock(sid):
            answers, synthesis, error = run_debate(sid, prompt, participants,
                                                   synthesizer, max_tokens)
        result = {"session_id": sid, "answers": answers, "synthesis": synthesis}
        if error:
            result["error"] = error
            return self._send_json(502, result)
        self._send_json(200, result)

    def _handle_get_session(self, sid):
        sess = get_session(sid)
        if not sess:
            return self._err(404, "not_found", f"session {sid}")
        sess["messages"] = get_messages(sid)
        self._send_json(200, sess)

    def do_DELETE(self):
        try:
            if self.path.startswith("/v1/memory/"):
                key = urllib.parse.unquote(self.path[len("/v1/memory/"):])
                delete_memory_key(key)
                return self._send_json(200, {"ok": True})
            if self.path.startswith("/v1/schedules/"):
                sid = urllib.parse.unquote(self.path[len("/v1/schedules/"):])
                return self._handle_schedule_del(sid)
            if self.path.startswith("/v1/tasks/"):
                tid = urllib.parse.unquote(self.path[len("/v1/tasks/"):])
                return self._handle_task_delete(tid)
            return self._err(404, "not_found", f"DELETE {self.path}")
        except Exception:
            tb = traceback.format_exc()
            safe_print(f"[proxy] UNHANDLED:\n{tb}")
            try:
                self._err(500, "internal", tb)
            except Exception:
                pass

    def _handle_memory_upsert(self):
        body = self._read_json()
        key = body.get("key")
        value = body.get("value")
        if not key or value is None:
            return self._err(400, "bad_request", "key and value required")
        if len(str(value)) > 10_000:
            return self._err(400, "bad_request", "value exceeds 10,000 character limit")
        entry = upsert_memory(key, str(value),
                              author=body.get("author", "user"),
                              tags=body.get("tags"))
        self._send_json(200, {"ok": True, "entry": entry})

    def _handle_continue(self, sid):
        sess = get_session(sid)
        if not sess:
            return self._err(404, "not_found", f"session {sid}")
        body = self._read_json()
        mode = sess["mode"]
        if mode == "debate":
            return self._err(400, "bad_request", "debates are one-shot")
        if mode == "pipeline":
            steps = body.get("steps") or []
            if not steps:
                return self._err(400, "bad_request", "steps required")
            existing = get_messages(sid)
            prior = existing[-1]["content"] if existing else sess["meta"].get("input", "")
            default_max = sess["meta"].get("max_tokens_per_step", 1024)
            start_turn = (max((m["turn_idx"] for m in existing), default=-1)) + 1
            with session_lock(sid):
                output, error = run_pipeline(sid, prior, steps, default_max,
                                             start_turn=start_turn)
            trace = [{"step": m["turn_idx"], "model": m["model"], "text": m["content"]}
                     for m in get_messages(sid)]
            result = {"session_id": sid, "output": output, "trace": trace}
            if error:
                result["error"] = error
                return self._send_json(502, result)
            return self._send_json(200, result)
        if mode == "room":
            turns = body.get("turns")
            if not turns:
                return self._err(400, "bad_request", "turns required")
            participants = sess["meta"]["participants"]
            topic = sess["meta"]["topic"]
            max_tokens = sess["meta"].get("max_tokens_per_turn", 512)
            existing = get_messages(sid)
            start_turn = (max((m["turn_idx"] for m in existing), default=-1)) + 1
            with session_lock(sid):
                transcript, error = run_room(sid, topic, participants, turns,
                                             max_tokens, start_turn=start_turn)
            result = {"session_id": sid,
                      "transcript": [{"turn": m["turn_idx"], "speaker": m["speaker"],
                                      "model": m["model"], "text": m["content"]}
                                     for m in transcript]}
            if error:
                result["error"] = error
                return self._send_json(502, result)
            return self._send_json(200, result)
        return self._err(400, "bad_request", f"unknown mode {mode}")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    key_status = "[OK]" if get_openrouter_key() else "[!!] not set - Kimi will fail"
    print("Glory proxy starting...")
    print(f"  Port            : {PORT}")
    print(f"  LM Studio       : {LM_STUDIO_URL} ({LM_STUDIO_MODEL})")
    print(f"  OpenRouter      : {OPENROUTER_URL} ({KIMI_MODEL})")
    print(f"  Sessions DB     : {DB_PATH}")
    print(f"  Modes enabled   : {GLORY_MODES_ENABLED}")
    print(f"  OpenRouter key  : {key_status}")
    bind_host = os.environ.get("PROXY_BIND_HOST", "0.0.0.0")
    server = http.server.ThreadingHTTPServer((bind_host, PORT), ProxyHandler)
    print(f"  Listening       : http://{bind_host}:{PORT}")
    server.serve_forever()


