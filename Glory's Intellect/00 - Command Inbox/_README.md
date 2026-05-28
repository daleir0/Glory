---
type: meta
---
# Command Inbox — How It Works

Drop a note here to give Glory a task.

## How to Create a Command

1. Create a new note in this folder
2. Name it anything descriptive (e.g., `Research Bitcoin ETFs.md`)
3. Use this structure:

---
type: command
created: YYYY-MM-DD
status: pending
priority: normal
---
# Task: [what you want done]

## Context
[any details, links, files Glory should know about]

## Output Location
[optional: where you want the output — defaults to appropriate folder]

---

## Priority Levels
- `high` — do this first
- `normal` — standard queue
- `low` — whenever

## Status Values
- `pending` — not yet started
- `in-progress` — Glory is working on it
- `done` — completed, safe to archive

## After Glory Completes
- Output will be in the appropriate folder
- This command note will be marked `status: done`
- Today's session log will reference it
