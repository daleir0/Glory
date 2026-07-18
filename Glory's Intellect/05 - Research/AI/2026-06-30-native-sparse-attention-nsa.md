---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2502.11089"
date: 2026-06-30
tags: [attention, sparse-attention, long-context, deepseek, kv-cache, inference, training, gqa]
---
# Native Sparse Attention (NSA): trainable hardware-aligned sparse attention with three parallel branches

## What
NSA (DeepSeek, Feb 2025; ACL 2025 best paper) replaces full attention with three sparse branches computed in parallel and fused by a learned gate per token:
1. **Compression** — consecutive tokens are pooled into block summary vectors → coarse global view at low cost.
2. **Selection** — importance scores pick the top-n *contiguous* KV blocks (contiguity = sequential memory reads, not random gather).
3. **Sliding window** — a fixed local window preserves recent-token precision.
Unlike post-hoc KV eviction (SnapKV) or inference-only sparse attention, NSA is **natively trainable end-to-end** — sparsity is learned during pretraining, so there is no train/inference mismatch. The kernel loads queries by GQA group (shared sparse KV blocks per group) to keep reads contiguous on SRAM. Reported: up to **11.6× decode speedup at 64k context** (memory-access bound), with forward/backward speedups too, validated on a 27B GQA+MoE model (270B tokens @8k, extended to 32k via YaRN) — matching or beating full attention on long-context and reasoning benchmarks.

## Why It Matters
This is the structural upgrade path beyond the eviction/quantization tricks already in Glory's stack ([[2026-06-26-snapkv-cache-eviction]], [[2026-05-29-kv-cache-quantization]]), which only trim an existing full-attention KV cache at inference. NSA changes the architecture so long-context cost scales sub-linearly *and the model is trained for it* — the right foundation if Glory ever trains or fine-tunes a long-context model rather than just serving one. Two immediate hooks: (1) it pairs with [[2026-06-01-multi-head-latent-attention-mla]] (NSA = sparse pattern, MLA = compressed KV; a Nov 2025 follow-up combines them) for compounding memory savings on the RTX 3060's tight VRAM ([[2026-05-18-rtx3060-optimal-llm-models]]); (2) the contiguous-block selection is the key insight — random top-k token gather kills GPU throughput, so any sparse-KV scheme Glory builds must select *blocks*, not tokens. Caveat: not yet a drop-in for llama.cpp GGUF serving — it requires the custom kernel and is a pretraining-time choice, so it's a model-design lever, not a runtime flag like [[2026-06-07-moe-expert-offloading-llama-cpp]].

## Source
- Paper: https://arxiv.org/abs/2502.11089 ("Native Sparse Attention: Hardware-Aligned and Natively Trainable Sparse Attention")
- ACL 2025: https://aclanthology.org/2025.acl-long.1126/
- Follow-up (NSA + latent attention, Nov 2025): https://arxiv.org/abs/2511.00819
- FSA alternative kernel (lower memory access for GQA=4): https://arxiv.org/abs/2508.18224

## Connected To
- [[2026-06-26-snapkv-cache-eviction]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-06-01-multi-head-latent-attention-mla]]
- [[2026-06-04-flash-attention-2-io-optimal-kernel]]
- [[2026-06-07-moe-expert-offloading-llama-cpp]]
- [[2026-05-18-rtx3060-optimal-llm-models]]
