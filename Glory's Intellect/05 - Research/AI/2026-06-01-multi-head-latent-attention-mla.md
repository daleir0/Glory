---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/pdf/2412.19437"
date: 2026-06-01
tags: [attention, kv-cache, mla, deepseek, transformer-variants, local-inference, memory-bandwidth]
---
# Multi-head Latent Attention (MLA): compressing the KV cache at the architecture level

## What
MLA (introduced in DeepSeek-V2, used in V2/V3/R1) replaces standard multi-head attention's per-token key/value storage with a single **low-rank latent vector**. Instead of caching full K and V (hidden_dim × heads × layers), MLA caches one compressed latent (e.g. a 4096-dim representation projected down to ~512 dims via a shared "KV-down" matrix) and **decompresses on demand** at attention time. DeepSeek-V3 reportedly stores ~70 KB/token vs ~516 KB/token for LLaMA-3.1 405B — a ~93% KV-cache reduction (8.7 GB vs 64.2 GB at 128K context).

Key mechanism — **weight absorption**: the K up-projection matrix can be folded into the query projection, so the QKᵀ score is computed directly in the compressed latent space and never materializes full K. This trades memory for FLOPs (MLA does ~4× the math of MHA), but modern GPU inference is **memory-bandwidth-bound, not compute-bound**, so reduced memory traffic wins net at 8K–128K contexts. Unlike GQA (which sheds quality to shrink the cache), MLA matched or slightly beat the MHA quality baseline in DeepSeek's ablations.

## Why It Matters
This is the architectural counterpart to two notes Glory already holds: KV-cache *quantization* (post-hoc compression of an existing cache) and speculative decoding (latency). MLA solves the same VRAM wall **at the model level** — and it directly explains why the large MoE models in Glory's routing stack (Kimi K2, DeepSeek-derived models) fit longer contexts than their parameter count suggests. For Glory's RTX 3060 (12 GB) reality, the lesson is concrete: when choosing a local model for long-context agentic work, an MLA-architecture model gives far more usable context per GB than an equivalently-sized MHA model. It also frames a future build decision — if Glory ever trains its own transformer (the "Glory AI" pillar via LLMs-from-scratch), MLA over MHA/GQA is the default for a memory-constrained deployment target. Caveat to verify before relying on it locally: llama.cpp's MLA path for DeepSeek-class models has matured but should be confirmed against the current build before assuming the absorption-aware kernel is active.

## Source
- DeepSeek-V3 Technical Report — https://arxiv.org/pdf/2412.19437
- Sebastian Raschka, "Multi-Head Latent Attention" — https://sebastianraschka.com/llms-from-scratch/ch04/05_mla/
- Chris McCormick, "Inner Workings of MLA" — https://mccormickml.com/2025/04/26/inner-workings-of-mla/
- "Towards Economical Inference: Enabling MLA in Any Transformer LLM" — https://arxiv.org/pdf/2502.14837

## Connected To
- [[2026-05-29-kv-cache-quantization]]
- [[2026-05-28-speculative-decoding-local-inference]]
- [[2026-05-18-kimi-k2-architecture]]
- [[2026-05-18-rtx3060-optimal-llm-models]]
