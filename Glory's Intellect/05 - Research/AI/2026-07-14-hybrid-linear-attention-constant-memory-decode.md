---
type: research-note
domain: AI
confidence: verified
source: "https://blog.vllm.ai/2025/09/11/qwen3-next.html"
date: 2026-07-14
tags: [linear-attention, mamba, ssd, gated-deltanet, hybrid-attention, kv-cache, long-context, local-inference, qwen3-next]
---
# Hybrid Linear-Attention: the 3:1 recipe that gives constant-memory decode without losing recall

## What
A linear-attention / state-space layer (Mamba-2, Gated DeltaNet) carries a
**fixed-size recurrent state** instead of a growing KV cache: decode is O(1)
memory and O(1) time per token, no matter the context length. Mamba-2's *State
Space Duality (SSD)* proves an SSM **is** a form of linear attention — the same
operation has a recurrent view (linear-time, O(1) decode) and a matmul view
(quadratic, fast parallel training). The catch: a fixed state is a lossy summary,
so pure-linear models are weak at *exact recall* (needle-in-a-haystack). The
winning 2025–26 fix is **hybrid**: interleave mostly-linear layers with a few
full softmax-attention layers. Qwen3-Next ships **3:1** — 32 layers as 8 blocks of
[3× Gated DeltaNet + 1× full Gated Attention]. That 25% softmax is enough to keep
needle-in-haystack, in-context learning, long chain-of-thought, and tool use;
the 75% linear layers erase most of the compute and KV-cache cost.

## Why It Matters
Every other KV-cache note in this vault *shrinks* a cache that still grows with
context — MLA compresses it, quantization halves its bytes, SnapKV/StreamingLLM
evict from it. Hybrid linear attention **structurally deletes** the cache in 75%
of layers: those layers store one fixed-size state, not one KV entry per past
token. On a 12GB 3060 that is the difference between "context length capped by
VRAM" and "context length capped by nothing" — the memory-bandwidth roofline that
makes decode memory-bound gets attacked at the source, because there is far less
per-token state to stream. This is where local long-context inference is going:
vLLM already runs Qwen3-Next; llama.cpp has Mamba/RWKV and is adding hybrid
support. The actionable takeaway is the *ratio* — you don't need pure-SSM purity
(which loses recall) or pure-transformer cost; ~3:1 linear:full is the empirically
validated sweet spot, and it's the shape of the next models Glory will run locally.

## Source
- https://blog.vllm.ai/2025/09/11/qwen3-next.html (Qwen3-Next hybrid: 3:1 Gated DeltaNet : full attention, every 4th layer full)
- https://tridao.me/blog/2024/mamba2-part3-algorithm/ (State Space Duality — SSM ≡ linear attention, recurrent vs matmul modes)
- https://sebastianraschka.com/llm-architecture-gallery/hybrid-attention/ (why hybrids beat pure-linear on recall)

## Connected To
- [[2026-06-01-multi-head-latent-attention-mla]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-06-30-native-sparse-attention-nsa]]
- [[2026-07-01-decode-memory-bandwidth-roofline]]
- [[2026-07-03-streamingllm-attention-sinks]]
