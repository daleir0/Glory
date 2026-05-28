# Glory's Intellect — Vault Design Spec
**Date:** 2026-04-17
**Status:** Approved

---

## Overview

Glory's Intellect is a true second-brain Obsidian vault designed for AI-human collaboration. The user ("Dalei") drops seeds, commands, and ideas; Glory (Claude Code) cultivates them into structured knowledge. The vault covers all domains with no limits — trading, crypto, programming, projects, research, ideas, and anything else.

---

## Architecture

### Folder Structure

```
D:\Glory\Glory's Intellect/
│
├── 00 - Command Inbox/        ← Drop a note here = task for Glory
│   └── _README.md
│
├── 01 - Sessions/             ← Dated logs of every interaction
│
├── 02 - Topics/               ← Living knowledge pages per subject
│
├── 03 - Trading/              ← Full trading domain
│   ├── Journal/
│   ├── Strategies/
│   ├── Watchlists/
│   └── Analysis/
│
├── 04 - Projects/             ← Goal → Plan → Execution → Outcome
│
├── 05 - Research/             ← Sourced deep dives
│
├── 06 - Ideas/                ← Raw captures, incubating
│
├── 07 - Atlas/                ← MOCs, indexes, vault map
│   ├── HOME.md
│   └── INDEX.md
│
├── 08 - Templates/            ← Reusable note skeletons
│
├── Wiki/                      ← General reference pages (encyclopedia-style)
├── raw-sources/               ← Source material (existing)
├── docs/                      ← Specs and meta-docs
└── _Archive/                  ← Completed/stale notes
```

### Organization Principles
- Top-level numbered folders for major domains (easy ordering)
- YAML frontmatter on every note for queryability
- Wikilinks for connections between notes
- Atlas MOCs as navigation hubs
- Sessions feed into Topics; Topics link to Projects

---

## Interaction Modes

### Bidirectional
- User writes seeds/thoughts in Obsidian
- Glory reads, expands, and structures them
- User reviews in Obsidian, redirects as needed

### Command-Driven
- User drops a note in `00 - Command Inbox/`
- Glory reads it, executes the task, routes output to correct folder
- Session log updated, command marked `status: done`

### Command Inbox Workflow
```
Drop note in 00 - Command Inbox/
        ↓
Glory reads and executes
        ↓
Output routed:
  Research      → 05 - Research/
  Topic update  → 02 - Topics/
  Trade analysis→ 03 - Trading/Analysis/
  Project plan  → 04 - Projects/
        ↓
Session log updated
        ↓
Command marked status: done
```

---

## Note Templates & Frontmatter Schema

### Command (Inbox)
```yaml
---
type: command
created: YYYY-MM-DD
status: pending # pending | in-progress | done
priority: high # high | normal | low
---
# Task: [what you want done]
## Context
```

### Session Log
```yaml
---
type: session
created: YYYY-MM-DD
tags: []
topics-touched: []
---
# Session — YYYY-MM-DD
## Commands Run
## Research Done
## Decisions Made
## Notes Updated
```

### Topic Page
```yaml
---
type: topic
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: growing # seed | growing | mature
tags: []
---
# [Topic Name]
## Overview
## Key Concepts
## Resources
## Connected Topics
## Session History
```

### Trade Journal Entry
```yaml
---
type: trade
date: YYYY-MM-DD
asset:
direction: long/short
entry:
exit:
result: win/loss/breakeven
tags: []
---
# Trade — [ASSET] [DATE]
## Setup
## Execution
## Outcome
## Lesson
```

### Project
```yaml
---
type: project
status: planning # planning | active | complete | archived
goal:
deadline:
tags: []
---
# [Project Name]
## Goal
## Plan
## Progress
## Outcome
```

### Research
```yaml
---
type: research
created: YYYY-MM-DD
topic:
sources: []
tags: []
---
# [Research Title]
## Summary
## Key Findings
## Sources
## Related Topics
```

### Idea
```yaml
---
type: idea
created: YYYY-MM-DD
status: raw # raw | developing | parked | promoted
tags: []
---
# [Idea Title]
## The Idea
## Why It Matters
## Next Steps
```

---

## Atlas Design

### HOME.md (vault front door)
- Quick links: Command Inbox, Trading Journal, INDEX
- Active Projects (live links)
- Recent Sessions (last 5)
- Hot Topics (most active)

### INDEX.md
- Full linked map of all topics, projects, research
- Organized by domain
- Updated whenever new major notes are created

---

## Scope

**In scope:**
- Full folder structure creation
- All templates
- HOME.md and INDEX.md in Atlas
- Command Inbox README
- Obsidian startup page set to HOME.md
- Seed content for core Topic pages (Trading, Crypto, Programming)
- Today's session log
- Migration of existing raw-sources content

**Out of scope:**
- Obsidian community plugins (user installs these manually)
- Dataview queries (added iteratively as vault grows)
- Automated syncing (handled by Obsidian Sync, already enabled)

---

## Success Criteria

1. Opening Obsidian lands on HOME.md
2. Dropping a note in Command Inbox triggers Glory's attention
3. Every folder has at least one template or seed note
4. Existing raw-sources content is linked into the new structure
5. Trading domain is fully scaffolded and ready for first journal entry
6. Atlas INDEX reflects the full vault map
