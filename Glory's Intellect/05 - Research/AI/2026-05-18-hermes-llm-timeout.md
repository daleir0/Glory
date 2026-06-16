---
type: research-note
domain: AI
confidence: verified
source: "Hermes status output — observation 1402, session May 17 2026"
date: 2026-05-18
tags: [hermes, timeout, lm-studio, inference, local-model]
---
# Hermes Timeout Values: 120s API, 360s Local Summarization

## What

Hermes sets two distinct timeout values: 120 seconds for standard LLM API calls, and 360 seconds for local model summarization tasks. These are hardcoded defaults visible in `hermes status` output.

## Why It Matters

Local models (e.g., gemma-4-e4b via LM Studio) can be slow to respond, especially for long prompts. The 120-second API timeout may fire before the model finishes generating if the prompt is complex or the GPU is under load. If a request silently times out, Hermes may return empty or error — check timeout first when debugging slow local inference.

## Source

Hermes status output, May 17 2026. Observation 1402.

## Connected To

- [[05 - Research/AI/2026-05-18-lm-studio-reasoning-content-field]]
- [[05 - Research/AI/2026-05-18-hermes-lmstudio-provider-alias]]
