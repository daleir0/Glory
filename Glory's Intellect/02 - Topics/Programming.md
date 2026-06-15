---
type: topic
created: 2026-04-17
updated: 2026-05-18
status: growing
tags: [programming, tech, tools, ai, claude, python, typescript]
---
# Programming

## Overview

Programming is the foundation of Glory AI — the languages, tools, frameworks, and patterns that make everything run. From local inference to multi-agent coordination to the Obsidian brain itself.

## Glory's Active Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Primary AI | Claude Sonnet 4.6 (`claude-sonnet-4-6`) | 1M context, extended thinking, 70% token efficiency |
| Agentic tasks | Kimi K2.6 via OpenRouter | 1T MoE, 300-agent swarms, SWE-Bench 65.8% |
| Local inference | Gemma 4 E4B via LM Studio (`127.0.0.1:1234`) | 256K context, PLE architecture, private data |
| Gateway | Hermes on WSL | Telegram, multi-provider routing |
| Proxy | glory-rooms proxy at `localhost:8082` | Routes to Claude / Kimi / Gemma |
| UI | glory-rooms Vite UI at `localhost:5173` | Multi-model browser environment |
| Vault | Glory's Intellect (Obsidian) | `D:\Glory\Glory's Intellect\` |
| Memory | claude-mem | Cross-session persistent memory DB |

## Languages

- **Python** — ML training (autoresearch), Hermes config, scripts
- **TypeScript/JavaScript** — glory-rooms UI (Vite), Node tooling
- **PowerShell** — Windows automation, PATH management
- **Bash** — WSL scripts, systemd, LM Studio interaction

## Key Patterns Learned

- [[05 - Research/Programming/2026-05-18-hermes-cli-flag-ordering|Hermes CLI: -z flag must precede subcommand]]
- [[05 - Research/Programming/2026-05-18-python-missing-deps-pattern|Python packages can ship incomplete dependencies]]
- [[05 - Research/Programming/2026-05-18-obsidian-mcp-server|Obsidian MCP server options for Claude Code]]
- [[05 - Research/Programming/2026-05-18-obsidian-dataview-plugin|Dataview plugin makes vault queryable as a database]]

## Upgrade Opportunities

1. **Obsidian MCP Server** — install to give Claude Code vault-native backlink/tag/graph access
2. **Dataview plugin** — make research notes auto-queryable by domain, confidence, date
3. **Prompt caching** — add to any Anthropic SDK code for 60–90% token cost reduction

## Session History

- 2026-04-17 — Topic page created, vault initialized
- 2026-05-18 — Updated with full Glory stack, research links, upgrade opportunities
