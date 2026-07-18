---
type: research-note
domain: AI
confidence: verified
source: "Kimi K2 technical report arxiv.org/abs/2507.20534; deepinfra.com/blog/kimi-k2-6-model-overview; eesel.ai/blog/kimi-k2.6"
date: 2026-05-18
tags: [kimi, k2, moe, agentic, model, openrouter, multi-agent]
---
# Kimi K2 Architecture — 1T MoE Designed for Agentic Tasks

## What

Kimi K2 is a 1.04 trillion-parameter Mixture-of-Experts (MoE) LLM with **32 billion activated parameters per token**. Developed by Moonshot AI. Built specifically for agentic tool use, not general chat.

K2.6 (latest variant) adds an **Agent Swarm primitive** that fans out to up to 300 domain-specialized sub-agents executing up to 4,000 coordinated steps.

Benchmark results (non-thinking mode):
- SWE-Bench Verified: **65.8%** (surpasses most open and closed-source)
- Tau2-Bench: **66.1%**
- ACEBench (En): **76.5%**
- DeepSearchQA: **92.5 F1** (web research + multi-hop reasoning)

Training: multi-stage post-training with large-scale agentic data synthesis pipeline + joint reinforcement learning against real and synthetic environments.

## Why It Matters

This is Glory's choice for **long autonomous agentic tasks** (12h+ runs, parallel agents). The MoE design means it activates 32B params per token — efficient at massive scale. The 300-agent swarm capability directly maps to Glory's multi-agent architecture in glory-rooms. When a task needs sustained autonomous execution without human checkpoints, Kimi K2 is the right model.

## Source

- [Kimi K2 Technical Report](https://arxiv.org/abs/2507.20534)
- [Kimi K2.6 Overview — DeepInfra](https://deepinfra.com/blog/kimi-k2-6-model-overview)
- [Kimi K2.6 Review — eesel AI](https://www.eesel.ai/blog/kimi-k2.6)

## Connected To

- [[05 - Research/AI/2026-05-18-claude-sonnet-4-6-capabilities]]
- [[project_glory_system]] (memory)
