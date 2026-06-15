---
type: research-note
domain: Programming
confidence: verified
source: "blacksmithgu.github.io/obsidian-dataview; obsidianstats.com/plugins/datacore; dsebastien.net/the-must-have-obsidian-plugins-for-2026"
date: 2026-05-18
tags: [obsidian, dataview, datacore, plugin, query, knowledge-base, yaml]
---
# Obsidian Dataview — Live Query Engine for the Vault

## What

Dataview is a live index and query engine for Obsidian. It reads YAML frontmatter from all notes and lets you query the vault like a database.

**Four query output types:**
- `TABLE` — tabular view with one row per note, custom columns
- `LIST` — bullet list of matching notes
- `TASK` — interactive task list
- `CALENDAR` — calendar view by date field

**Basic query structure:**
```dataview
TABLE domain, confidence, date
FROM "05 - Research"
WHERE type = "research-note"
SORT date DESC
```

**Datacore** (2026 successor): React-based JS API, faster queries, stateful flicker-free rendering. More powerful but more complex.

Glory's research notes already use Dataview-compatible frontmatter fields: `type`, `domain`, `confidence`, `date`, `tags`.

## Why It Matters

Installing Dataview would make Glory's research sector fully queryable. You could write a single note with an embedded query that shows all research notes by domain, all `uncertain` confidence items, or all notes from this week — auto-updating as new notes are added. This turns the vault from a folder of files into an actual live database. The frontmatter schema is already in place.

**Action:** Install Dataview plugin in Obsidian → Settings → Community Plugins → search "Dataview".

## Source

- [Dataview Docs](https://blacksmithgu.github.io/obsidian-dataview/)
- [Best Obsidian Plugins 2026 — Sébastien Dubois](https://www.dsebastien.net/the-must-have-obsidian-plugins-for-2026/)

## Connected To

- [[05 - Research/_INDEX]]
- [[05 - Research/Programming/2026-05-18-obsidian-mcp-server]]
