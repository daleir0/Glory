---
type: research-note
domain: AI
confidence: verified
source: "https://kellerjordan.github.io/posts/muon/"
date: 2026-05-26
tags: [optimizer, training, muon, adamw, newton-schulz, orthogonalization, convergence]
---
# Muon Optimizer: SGD Momentum + Newton-Schulz Orthogonalization Beats AdamW

## What
Muon (MomentUm Orthogonalized by Newton-Schulz) is an optimizer for hidden weight matrices, introduced by Keller Jordan in December 2024. It applies standard SGD-with-momentum, then orthogonalizes each 2D update via a fast Newton-Schulz iteration, then applies the result with aspect-ratio scaling. Embeddings, classifier heads, and biases still use AdamW — Muon is only for hidden weight layers. Newton-Schulz runs stably in bfloat16 on GPU, making the extra step cheap.

## Why It Matters
Muon strictly lower-bounds AdamW on training loss throughout the run with no crossover. On a 1.5B-parameter transformer, it reached GPT-2 XL quality on HellaSwag in 10 8×H100-hours vs 13.3 hours for AdamW — a 1.33× speedup. Memory overhead is ~33% lighter than AdamW's optimizer states. The autoresearch experiments at `E:\Glory\autoresearch` use AdamW; swapping hidden-layer parameters to Muon is a direct, low-risk improvement to try on the next run. Drop-in via `pip install muon`.

## Source
https://kellerjordan.github.io/posts/muon/
GitHub: https://github.com/KellerJordan/Muon
Benchmarks: https://arxiv.org/html/2505.02222v1

## Connected To
- [[autoresearch-hyperparameter-search]]
- [[karpathy-nanoGPT]]
- [[adam-optimizer]]
