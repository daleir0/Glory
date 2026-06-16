---
type: research-note
domain: AI
confidence: verified
source: "platform.claude.com/docs/en/build-with-claude/prompt-caching; aimagicx.com/blog/prompt-caching-claude-api; tokenmix.ai/blog/claude-api-cache-pricing"
date: 2026-05-18
tags: [claude, prompt-caching, token-savings, api, cost-optimization]
---
# Claude Prompt Caching — 60–90% Token Cost Reduction

## What

Claude's prompt caching feature caches the prefix of a prompt (system prompt, tools, large documents) for reuse across requests.

**Pricing tiers:**
| Action | Cost |
|--------|------|
| Cache write (5-min TTL) | 1.25x base input rate |
| Cache write (1-hour TTL) | 2.0x base input rate |
| Cache read | **0.1x base input rate** (90% cheaper) |

**Minimum cacheable size:** 1,024 tokens for Sonnet 4.6.

**Break-even:** 3+ reads within 5-min TTL; 5+ reads within 1-hour TTL.

**Concrete example:** A 30,000-token system prompt costs $0.09/request uncached on Sonnet 4.6 ($3/M). With a cache hit: $0.009 — 90% reduction.

**Automatic caching:** Add a single `cache_control` field at the top level of the request body. The system automatically applies the breakpoint to the last cacheable block. No need to manually tag every block.

**Prompt structure rule:** Static content (system prompt, tools, documents) must come **first**. Dynamic content (user message, conversation history) comes **last**. This ensures the static prefix is cacheable.

**2026 update:** Cache-read tokens no longer count against ITPM rate limits — high-throughput cached workflows are now unblocked.

## Why It Matters

Glory makes repeated API calls with the same Glory system prompt, CLAUDE.md, and tool definitions every session. These are prime caching candidates. Implementing caching on Glory's Anthropic SDK code could cut API costs 60–90% immediately. The SOUL.md persona in Hermes is also a prime cache candidate.

## Source

- [Prompt Caching Docs — Anthropic](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [90% Savings Explained — TokenMix](https://tokenmix.ai/blog/claude-api-cache-pricing)

## Connected To

- [[05 - Research/AI/2026-05-18-claude-sonnet-4-6-capabilities]]
