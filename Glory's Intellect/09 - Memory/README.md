---
type: meta
created: 2026-04-17
tags: [memory, claude-mem, system]
---
# Memory System — How It Works

Glory's Intellect uses **claude-mem** for persistent memory that works across all AI models and sessions.

---

## What claude-mem Does

Every session with Claude Code is automatically observed and summarized into a persistent database. This means:

- **Cross-session recall** — Glory remembers past conversations, decisions, and work
- **Cross-model** — Memory works whether you're using Claude, a local LM Studio model, or any other provider
- **Automatic** — No manual effort needed; claude-mem captures everything in the background

---

## Memory Database Location

```
C:\Users\dalei\.claude-mem\claude-mem.db
```

The database uses SQLite + ChromaDB (vector search) for semantic retrieval.

---

## How to Query Memory

Inside any Claude Code session, Glory can search memory using:

```
Search for: "trading strategy" → finds all past observations about trading
Timeline: anchor around an observation ID → see surrounding context
Get: specific observation IDs → read full details
```

---

## Memory Export to Vault

To make memories visible in Obsidian, run a memory export:

1. Ask Glory: *"Export recent memory observations to the vault"*
2. Glory will write a snapshot to `09 - Memory/exports/YYYY-MM-DD-snapshot.md`
3. Open in Obsidian to browse past work

---

## Cross-Model Memory

claude-mem works with any model because it's a separate background process. The memory worker observes your Claude Code sessions and stores summaries regardless of which underlying model is active.

Supported providers configured:
- **Claude** (primary) — routes through `ANTHROPIC_BASE_URL`
- **OpenRouter** — configure API key in claude-mem settings for additional models
- **Gemini** — configure API key for Google models

---

## Settings

claude-mem settings live at:
```
C:\Users\dalei\.claude-mem\settings.json
```

Key settings for this vault:
- `CLAUDE_MEM_FOLDER_CLAUDEMD_ENABLED: true` — injects vault CLAUDE.md into sessions
- `CLAUDE_MEM_DATA_DIR` — where the database lives
- `CLAUDE_MEM_PROVIDER` — which AI processes memories

---

## Related
- [[07 - Atlas/HOME|HOME]]
- [[02 - Topics/Programming|Programming]]
