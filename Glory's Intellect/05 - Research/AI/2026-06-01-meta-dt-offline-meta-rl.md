---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2410.11448"
date: 2026-06-01
tags: [meta-rl, offline-rl, decision-transformer, world-model, in-context-adaptation, agent-memory]
promoted_from: gemma+hermes draft
---
# Meta-DT: Task Adaptation Without Retraining, via World-Model-Guided Prompts

## What
Meta-DT (NeurIPS 2024, Wang et al.) makes a Decision Transformer generalize to *new* tasks at test time with **no expert demonstrations and no fine-tuning**. It works in two moves:

1. **World-model disentanglement** — a context-aware world model is pretrained to compress each task into a compact representation, which is then injected as a conditioning token into a causal transformer. Task identity is *factored out* of the policy and carried by the representation.
2. **Error-guided prompting** — instead of a random or expert prompt, it selects the trajectory segment where the pretrained world model has the **largest prediction error**. That segment is, by construction, the part of the new task the model doesn't yet understand — so it carries the most task-specific information complementary to what the world model already encodes.

Result: superior few-shot and zero-shot generalization on MuJoCo and Meta-World vs strong baselines, with fewer prerequisites at deployment.

## Why It Matters for Glory
This is a direct blueprint for two pillars of Glory's stack:

- **Autoresearch (`E:\Glory\autoresearch`)** currently trains models per-config from scratch. Meta-DT's offline-meta-RL framing means Glory could learn a *single* policy that adapts to a new hyperparameter regime or task from its own logged trajectories — turning every past training run into reusable conditioning data instead of a throwaway experiment.
- **Agent memory / in-context adaptation.** The error-guided prompt selection is the sharp idea: *the most valuable context is the part the model predicts worst.* Glory's memory retrieval (and the local research loop here) currently surfaces the most *similar* past material. Meta-DT argues for surfacing the most *surprising* — highest-prediction-error — material instead. That's a concrete, testable change to how Glory picks what to load into context: retrieve by novelty/surprise, not just similarity.

The transferable principle for Glory's reasoning: **condition on a compact task vector + the single most-surprising trajectory, not a pile of similar examples.** Cheaper context, better generalization.

## Open Question / Next Step
Test the "retrieve by prediction error, not similarity" hypothesis on Glory's own memory: when loading prior research into context, rank candidates by how poorly the current model predicts them and prefer the surprising ones. Cheap to prototype against the existing `_drafts/` corpus.

## Source
- Paper: https://arxiv.org/abs/2410.11448 (NeurIPS 2024)
- Authors: Zhi Wang, Li Zhang, Wenhao Wu, Yuanheng Zhu, Dongbin Zhao, Chunlin Chen

## Connected To
- [[autoresearch-hyperparameter-search]]
- [[2026-05-26-muon-optimizer]]

---
*Tier-2 note: promoted and verified by Claude from a Gemma + Hermes Tier-1 draft.*
