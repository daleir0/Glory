---
type: research-note
domain: AI
confidence: verified
source: "https://cameronrwolfe.substack.com/p/grpo"
date: 2026-06-02
tags: [rl, training, reinforcement-learning, deepseek, reasoning, post-training, optimizer]
---
# GRPO: Group Relative Policy Optimization

## What
GRPO eliminates the critic/value network that PPO requires. For each prompt, sample N=8–64 completions, score each with a rule-based reward function, then compute advantage as `(reward - group_mean) / group_std`. The normalized advantages drive the policy gradient update — no separate critic model, no trained reward model needed. Introduced in DeepSeekMath; scaled to general reasoning in DeepSeek-R1.

## Why It Matters
PPO requires four models in memory simultaneously: policy, frozen reference, critic, and reward model. On a 12 GB RTX 3060, that's prohibitive. GRPO cuts memory 40–60% by dropping the critic entirely. It also eliminates reward model training — rewards are rule-based (format check, answer correctness), which means Glory can implement GRPO fine-tuning on Gemma 4 using only a Python verifier function as the reward signal. DeepSeek-R1-Zero proved that pure GRPO with no SFT cold-start can bootstrap emergent chain-of-thought reasoning from scratch.

## Source
- https://cameronrwolfe.substack.com/p/grpo
- https://huggingface.co/blog/karina-zadorozhny/guide-to-llm-post-training-algorithms
- https://ghost.oxen.ai/why-grpo-is-important-and-how-it-works/

## Connected To
- [[meta-dt-offline-meta-rl]]
- [[muon-optimizer]]
- [[kv-cache-quantization]]
