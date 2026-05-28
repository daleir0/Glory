---
type: research-note
domain: Programming
confidence: verified
source: "github.com/iansinnott/obsidian-claude-code-mcp; github.com/MarkusPfundstein/mcp-obsidian; markanamedia.com/blog/obsidian-mcp-server-claude-code"
date: 2026-05-18
tags: [obsidian, mcp, claude-code, integration, vault, backlinks, search]
---
# Obsidian MCP Server — Claude Code Direct Vault Access

## What

An Obsidian MCP server gives Claude Code first-class, vault-aware access to Glory's Intellect beyond raw file reads. Two main options in 2026:

**Option A — obsidian-claude-code-mcp (iansinnott):**
- Claude Code connects to Obsidian via WebSocket on port 22360
- Requires Obsidian to be running with a companion plugin
- Vault-native operations: backlinks, tags, daily notes, graph-aware search

**Option B — mcp-obsidian (MarkusPfundstein) — most established (3,000 stars):**
- Requires "Local REST API" community plugin in Obsidian
- Obsidian must be running
- Full CRUD operations via REST

**Option C — Zero-dependency file reader (newest, March 2026):**
- No Obsidian plugins required
- Works even when Obsidian is not open
- BM25 full-text search with relevance ranking
- Handles frontmatter safely
- Reads raw `.md` files directly

**Installation (npm):**
```bash
npm install -g obsidian-mcp
# Then configure in Claude Code settings
```

## Why It Matters

Currently Claude Code accesses the vault via raw file tools (Read, Write, Edit). An MCP server would unlock vault-native operations impossible with file access alone: "find every orphan note in my vault," "show all notes linking to this research note," "search by tag across all domains." This would make the research sector dramatically more powerful — Claude could navigate the knowledge graph, not just individual files.

The zero-dependency option (Option C) is the easiest to set up since it doesn't require Obsidian to be open during Claude Code sessions.

## Source

- [obsidian-claude-code-mcp — GitHub](https://github.com/iansinnott/obsidian-claude-code-mcp)
- [mcp-obsidian — GitHub](https://github.com/MarkusPfundstein/mcp-obsidian)

## Connected To

- [[05 - Research/Programming/2026-05-18-obsidian-dataview-plugin]]
- [[05 - Research/_INDEX]]
