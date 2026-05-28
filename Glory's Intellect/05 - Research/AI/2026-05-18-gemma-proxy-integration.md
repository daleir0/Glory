---
type: research-note
domain: AI
confidence: verified
source: "Direct inspection of D:\\Glory\\glory-rooms\\proxy\\lm-proxy.py — May 18 2026"
date: 2026-05-18
tags: [gemma, lm-studio, proxy, glory-rooms, routing, local-inference]
---
# Gemma Integration in glory-rooms Proxy

## What

Gemma 4 E4B (`google/gemma-4-e4b`) is the **default local backend** in `lm-proxy.py`. It runs via LM Studio at `http://169.254.83.107:1234` (link-local Windows host IP from WSL).

**Routing rules:**
- `/v1/messages` (Anthropic format): default → gemma; KIMI_ALIASES → kimi; QWEN_ALIASES → qwen
- `/v1/chat/completions` (OpenAI format): default → kimi; KIMI_ALIASES → kimi; QWEN_ALIASES → qwen; else → gemma

**Explicit Gemma aliases** (added 2026-05-18):
`"gemma"`, `"gemma-4"`, `"gemma-4-e4b"`, `"google/gemma-4-e4b"`, `"local"`, `"fast"`, `"private"`

**Best use cases for Gemma in Glory:**
- Fast local responses (no API latency)
- Private data (stays on-machine)
- Pre-processing/summarization steps in pipelines
- Fallback when OpenRouter is down
- Low-stakes quick tasks where 256K context is enough

**Config vars:**
- `GEMMA_TIMEOUT` = 120s (env-configurable)
- `LM_STUDIO_MODEL` = `"google/gemma-4-e4b"`
- `LM_STUDIO_HOST` = env var `LM_STUDIO_HOST`, default `169.254.83.107`

## Why It Matters

Gemma is the privacy layer of Glory's stack — any prompt involving sensitive data should route to Gemma. It's also the fastest path since there's no network round-trip to OpenRouter. Prompt cleaning (added same session) applies to Gemma calls specifically since local models benefit most from lean, well-structured input.

## Source

Direct inspection of `D:\Glory\glory-rooms\proxy\lm-proxy.py`, lines 44-60, 432-476, 1260-1288.

## Connected To

- [[05 - Research/AI/2026-05-18-gemma-4-e4b-architecture]]
- [[05 - Research/AI/2026-05-18-lm-studio-reasoning-content-field]]
- [[05 - Research/Systems/2026-05-17-wsl-mirrored-networking]]
