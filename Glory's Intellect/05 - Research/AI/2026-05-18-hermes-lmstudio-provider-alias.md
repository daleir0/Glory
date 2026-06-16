---
type: research-note
domain: AI
confidence: verified
source: "Hermes providers module inspection — observation 1401, session May 17 2026"
date: 2026-05-18
tags: [hermes, lm-studio, provider, configuration]
---
# Hermes Recognizes "lmstudio" as a Dedicated Provider Alias

## What

Hermes's providers module has a dedicated alias `lmstudio` that routes requests to LM Studio's local inference endpoint. It is not a generic OpenAI-compatible provider — it is explicitly recognized and has dedicated handling code.

## Why It Matters

When configuring Hermes to use LM Studio, the correct provider string is `lmstudio` (not `openai`, `local`, or any other alias). Using the wrong provider string will cause incorrect routing, header handling, or response parsing.

## Source

Hermes providers module inspection during May 17 2026 debugging session. Observation 1401.

## Connected To

- [[05 - Research/AI/2026-05-18-lm-studio-reasoning-content-field]]
- [[05 - Research/AI/2026-05-18-hermes-llm-timeout]]
