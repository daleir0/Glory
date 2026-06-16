---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2205.14135"
date: 2026-06-04
tags: [attention, flash-attention, inference, local-inference, memory-bandwidth, CUDA, ampere, llama-cpp, kernels, transformer]
---
# Flash Attention 2: IO-optimal attention and why Ampere (RTX 3060) benefits from it

## What
Standard attention materializes the full N×N attention score matrix in GPU HBM (high-bandwidth memory) — at 4K context length, that's 4096² × fp16 = 32 MB **per layer**, written and re-read for each forward pass. FlashAttention (FA1, 2022; FA2, 2023) rewrites the algorithm to tile QK^T matmul and the softmax into SRAM-sized blocks, using **online softmax** to accumulate the result incrementally. The full attention matrix is **never materialized in HBM**. Result: HBM access drops from O(N²) to O(N²d²/M) — up to 9× fewer HBM reads/writes for typical head dims (d=64–128) and SRAM sizes.

FA2 adds three improvements over FA1: (1) splits the outer loop over Q rather than K/V, doubling the proportion of compute that's in pure matmuls; (2) reduces non-matmul FLOPs by ~50%; (3) achieves ~70% of theoretical peak FLOPs on A100 (up from ~35% for FA1). FA2 supports **Ampere, Ada, and Hopper** GPUs — the RTX 3060 (sm_86, Ampere) is fully supported. FA3 (2024) requires **Hopper only** (H100/H800, sm_90, CUDA ≥ 12.3) and is not available on any consumer GPU.

In llama.cpp, Flash Attention is enabled via `--flash-attn` (or `-fa`). It is opt-in (not default) and requires a CUDA build; Vulkan builds use a separate path.

## Why It Matters
At 32 layers and 4K context, attention matrix HBM traffic per forward pass is ~1 GB without FA — pure bandwidth cost before any model weight I/O. On the RTX 3060's 360 GB/s HBM2X bus, that's ~2.8 ms of pure memory wall per forward step, which compounds across every decoding token. FA2 eliminates this entirely, keeping attention computation inside the 128 KB L1/shared memory per SM and reducing decode latency directly.

For Glory's local inference stack: enabling `--flash-attn` in llama.cpp is the single highest-leverage flag for long-context agentic sessions (tool-heavy, multi-turn). It doesn't improve throughput at short contexts (< 512 tokens) where the full N×N matrix already fits in cache, but above 2K tokens it is strictly better — faster AND lower VRAM usage. This note completes the inference efficiency stack alongside the KV-cache quantization (post-hoc cache compression), MLA (architecture-level cache compression), and PagedAttention (dynamic VRAM allocation) notes.

FA3's Hopper exclusivity closes the path for RTX 3060 upgrade via software: there is no FA3 benefit to extract on Ampere. The practical ceiling is FA2 + llama.cpp CUDA build + Q4/Q5 weights.

## Source
- FlashAttention original paper: https://arxiv.org/abs/2205.14135
- FA2 paper (Tri Dao, 2023): https://arxiv.org/abs/2307.08691
- FA3 blog (Hopper-only): https://tridao.me/blog/2024/flash3/
- llama.cpp FA benchmarks: https://knightli.com/en/2026/04/23/llama-cpp-gpu-benchmark-cuda-rocm-vulkan-scoreboard/
- IO-complexity analysis: https://huggingface.co/blog/atharv6f/flash-attention-io-analysis

## Connected To
- [[2026-06-03-pagedattention-continuous-batching]]
- [[2026-06-01-multi-head-latent-attention-mla]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-05-28-speculative-decoding-local-inference]]
- [[2026-05-18-rtx3060-optimal-llm-models]]
