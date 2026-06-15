---
type: research-note
domain: Programming
confidence: verified
source: "Implemented in D:\\Glory\\glory-rooms\\proxy\\lm-proxy.py — May 18 2026"
date: 2026-05-18
tags: [prompt-cleaning, lm-studio, gemma, proxy, pipeline, context-management]
---
# Prompt Cleaning — Normalize Messages Before Local Inference

## What

`clean_messages(messages, max_tokens=None)` — a preprocessing function applied to every message list before it reaches a local model (Gemma, Qwen via LM Studio).

**Four steps:**
1. **Stringify** — flattens Anthropic multi-part content blocks to plain text
2. **Strip** — removes leading/trailing whitespace from every message
3. **Merge** — consecutive same-role messages are joined with `\n\n` (reduces context noise)
4. **Truncate** — if `max_tokens` set, drops middle turns to fit budget while preserving system messages and the final user message

**Budget constants (env-configurable):**
- `LOCAL_PROMPT_TOKENS` — default `32000` tokens (128K chars) before truncation
- `_CHARS_PER_TOKEN` = 4 (conservative estimate)

**Applied at:** `lmstudio_call()` — every call to Gemma or Qwen automatically gets cleaned input.

## Why It Matters

Local models (especially Gemma E4B) are fast but sensitive to bloated or malformed input. Cleaned prompts:
- Reduce token consumption → faster inference, more KV cache headroom
- Avoid errors from malformed multi-part content blocks passed from Anthropic-format callers
- Prevent context overflow on long pipeline chains by dropping stale middle turns
- Merge noisy split messages from streaming pipelines into coherent context

The budget default (32K tokens) is conservative for Gemma's 256K context — raise `LOCAL_PROMPT_TOKENS` if Glory needs deeper history in local calls.

## Source

Implemented in `D:\Glory\glory-rooms\proxy\lm-proxy.py` after line 432. Added to `lmstudio_call()` at model call entry point.

## Connected To

- [[05 - Research/AI/2026-05-18-gemma-proxy-integration]]
- [[05 - Research/AI/2026-05-18-gemma-4-e4b-architecture]]
- [[05 - Research/Hardware/2026-05-18-rtx3060-optimal-llm-models]]
