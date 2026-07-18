---
type: research-note
domain: AI
confidence: verified
source: "Direct curl test to LM Studio 127.0.0.1:1234 returned valid content field; Hermes returned empty — observation 1403, 1417, session May 17 2026"
date: 2026-05-18
tags: [lm-studio, hermes, api, inference, debugging]
---
# LM Studio Returns content, But Hermes Sees Empty — Pipeline Bug Not Model Bug

## What

When calling LM Studio directly via curl, the model returns a valid, non-empty `content` field in the response. However, Hermes (the gateway) reported an empty response. The emptiness was caused by a bug or misconfiguration in Hermes's response parsing pipeline — not the model itself.

## Why It Matters

Diagnosing "empty response from model" failures must distinguish between: (1) the model actually producing nothing, and (2) the pipeline failing to extract the response. Testing the model directly via curl bypasses the pipeline and isolates the actual model behavior. Always curl directly first before assuming the model is at fault.

## Source

Session May 17 2026: direct `curl http://127.0.0.1:1234/v1/chat/completions` returned valid content. `hermes chat` returned empty for the same model (gemma-4-e4b). Observations 1403, 1416, 1417.

## Connected To

- [[05 - Research/AI/2026-05-18-hermes-lmstudio-provider-alias]]
- [[05 - Research/Systems/2026-05-17-wsl-mirrored-networking]]
