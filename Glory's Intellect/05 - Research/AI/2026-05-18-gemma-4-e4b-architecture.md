---
type: research-note
domain: AI
confidence: verified
source: "blog.google/innovation-and-ai/technology/developers-tools/gemma-4; gemma4.wiki; lmstudio.ai/models/gemma-4"
date: 2026-05-18
tags: [gemma, google, local-inference, lm-studio, multimodal, thinking, architecture]
---
# Gemma 4 (E4B) — Architecture and Local Inference Characteristics

## What

Gemma 4 is Google's 2026 open model family with four variants: **E2B, E4B, 26B MoE, 31B dense**.

Glory runs **gemma-4-e4b** locally via LM Studio.

Key architecture notes for E2B/E4B:
- Uses **PLE (Parameter-efficient Local Execution)** — NOT MoE. A different efficiency strategy optimized for mobile and consumer GPU inference.
- Native multimodality: text, image (variable resolution), video, audio
- **256K token context window**
- Configurable **thinking mode** (extended reasoning on/off)
- Full GGUF/llama.cpp support for local inference

The 26B and 31B variants use MoE blocks added as separate layers alongside standard MLP blocks (outputs summed) — an unusual design that trades some efficiency for architectural simplicity.

Gemma 4 is fully available in LM Studio as of 2026.

## Why It Matters

The E4B fits on Glory's RTX 3060 (12GB VRAM) with room to spare. The 256K context window is massive for a local model — suitable for reading entire codebases or large documents locally and privately. The thinking mode means E4B can do extended reasoning locally, which is valuable for private/sensitive tasks that shouldn't leave the machine. Video and audio inputs on E4B are a future capability to explore.

## Source

- [Gemma 4 — Google Blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)
- [Gemma 4 in LM Studio](https://lmstudio.ai/models/gemma-4)

## Connected To

- [[05 - Research/AI/2026-05-18-hermes-lmstudio-provider-alias]]
- [[05 - Research/Hardware/2026-05-18-rtx3060-optimal-llm-models]]
