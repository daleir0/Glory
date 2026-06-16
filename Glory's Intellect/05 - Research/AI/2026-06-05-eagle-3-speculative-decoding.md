---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2503.01840"
date: 2026-06-05
tags: [speculative-decoding, inference, eagle, draft-model, local-inference, throughput]
---
# EAGLE-3: training-time test + multi-layer fusion pushes speculative decoding to 6.5x

## What
EAGLE-3 is the current state-of-the-art speculative-decoding draft head. It makes two changes over EAGLE-2: (1) it **drops feature prediction** — the draft model directly predicts the *next token* instead of being forced to regress the target model's top-layer hidden state, removing an error-accumulation constraint; and (2) it feeds the draft model a **fusion of low-, mid-, and high-layer features** from the base model (concatenated, then projected down through one FC layer) instead of only the top layer. To prevent the draft head from overfitting to single-step teacher-forced features, it trains with a **"training-time test"** that simulates multi-step autoregressive drafting during training. Result: up to **6.5x** wall-clock speedup (≈1.4x over EAGLE-2) and ~1.38x throughput at batch size 64 in SGLang. Critically, EAGLE-3 unlocks a **scaling law** — unlike EAGLE-1/2, draft accuracy keeps improving as you add training data (trained on ~532K examples: ShareGPT 68K + UltraChat-200K 464K).

## Why It Matters
Glory runs local inference on a 12GB RTX 3060 where it is **memory-bandwidth bound**, not compute bound — every forward pass drags the full weight matrix through VRAM, so generating one token costs nearly the same as verifying several. That is exactly the regime speculative decoding exploits: a cheap draft proposes k tokens, the target verifies them all in one batched pass, and accepted tokens are free. EAGLE-3 raises the acceptance length per draft, which directly multiplies tokens/sec on Gemma/Qwen-class local models without changing output distribution (lossless — verification guarantees identical samples). The scaling-law finding is the actionable insight: a self-hosted draft head trained on Glory's own traffic logs (synthesis prompts, HYPE narratives, agent chatter) should keep getting faster as we accumulate data — it compounds. Both `llama.cpp` and SGLang/vLLM now ship EAGLE-style speculative paths, so this is deployable in Glory's stack today, layered on top of the [[2026-06-03-pagedattention-continuous-batching|PagedAttention]] KV-cache management already in use.

## Source
- Paper: https://arxiv.org/abs/2503.01840 (EAGLE-3: Scaling up Inference Acceleration of LLMs via Training-Time Test, NeurIPS 2025)
- Code: SafeAILab/EAGLE (GitHub)
- Practical benchmark guide: https://www.e2enetworks.com/blog/Accelerating_LLM_Inference_with_EAGLE

## Connected To
- [[2026-05-28-speculative-decoding-local-inference]]
- [[2026-06-03-pagedattention-continuous-batching]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-06-01-multi-head-latent-attention-mla]]
