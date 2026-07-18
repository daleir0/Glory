---
type: research-note
domain: AI
confidence: verified
source: "anthropic.com/news/claude-sonnet-4-6; claudefa.st/blog/models/claude-sonnet-4-6; datacamp.com/blog/claude-sonnet-4-6"
date: 2026-05-18
tags: [claude, sonnet, anthropic, capabilities, context-window, computer-use, coding]
---
# Claude Sonnet 4.6 — Key Capabilities

## What

Released February 17, 2026. Model ID: `claude-sonnet-4-6`. This is the model powering Glory's primary Claude Code sessions.

Key specs:
- **Context window:** 1M tokens (beta)
- **Extended thinking:** fine-grained API control over thinking effort; near-instant or deep step-by-step reasoning
- **Computer use:** 72.5% on OSWorld Verified — most capable Claude computer use model
- **Token efficiency:** 70% fewer tokens + 38% more accurate than Sonnet 4.5 on internal filesystem evals
- **Pricing:** $3 input / $15 output per million tokens (same as 4.5)
- **Prompt injection resistance:** major improvement over 4.5, on par with Opus 4.6
- **Coding:** developers preferred it over Opus 4.5 in early access

Cache-aware rate limits: prompt cache read tokens no longer count against ITPM limit — high-throughput caching workflows are now unblocked.

## Why It Matters

This is the model running right now in Glory's sessions. Understanding its actual capabilities — especially the 1M context window, extended thinking, and token efficiency — directly shapes how tasks should be structured. The 70% token reduction means Glory's long-context workflows (reading large codebases, multi-file edits) should lean into the model's natural efficiency rather than trying to compress context manually.

## Source

- [Introducing Claude Sonnet 4.6 — Anthropic](https://www.anthropic.com/news/claude-sonnet-4-6)
- [Claude Sonnet 4.6 Specs — claudefa.st](https://claudefa.st/blog/models/claude-sonnet-4-6)

## Connected To

- [[05 - Research/AI/2026-05-18-claude-prompt-caching]]
- [[05 - Research/AI/2026-05-18-kimi-k2-architecture]]
