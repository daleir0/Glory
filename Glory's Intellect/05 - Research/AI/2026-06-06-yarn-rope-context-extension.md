---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2309.00071"
date: 2026-06-06
tags: [context-window, rope, yarn, long-context, llama-cpp, local-inference, attention]
---
# YaRN: extending a model's context window by reshaping RoPE frequencies + scaling attention temperature

## What
YaRN ("Yet another RoPE extensioN", Peng et al. 2023, arXiv 2309.00071) extends the usable context window of any RoPE-based model (LLaMA, Qwen, Mistral, DeepSeek, gpt-oss) far beyond its trained length. It combines two moves:

1. **NTK-by-parts interpolation** — instead of uniformly stretching all positions (linear/PI scaling, which destroys high-frequency detail), YaRN splits RoPE dimensions by *wavelength*. High-frequency dims (short wavelength, encode local/token-adjacent relations) are left untouched; low-frequency dims (long wavelength, encode long-range position) are interpolated to the new length; a ramp function controlled by α (ramp start) and β (ramp end) smoothly blends the middle band. For LLaMA the paper uses α=1, β=32.
2. **Attention temperature scaling** — as context grows, attention entropy drifts out of the regime the model trained in (logits get too sharp/flat). YaRN multiplies the q·k logits by a factor √(1/t) where √(1/t) ≈ 0.1·ln(s) + 1 (s = the extension scale factor). Crucially this is folded into the precomputed cos/sin RoPE tables, so it costs **zero extra FLOPs at inference**.

The result: ~10× fewer tokens and ~2.5× fewer training steps than prior extension methods to reach the same long-context quality. With light fine-tuning a 4k model reaches 64k–128k; "Dynamic-YaRN" applies scaling only as the sequence actually grows, giving >2× extension with *no* fine-tuning.

## Why It Matters
Glory runs Gemma / Qwen / Kimi locally via llama.cpp on a 12 GB RTX 3060. Native context is often the binding constraint for agentic memory, long research notes, and multi-file code work. YaRN is the lever to push past native context **without retraining and without inference overhead** — the agentic-memory and long-document workflows live or die on this. Practical llama.cpp invocation:

```
--rope-scaling yarn --rope-scale <factor> --yarn-orig-ctx <native_ctx> -c <target_ctx>
```

e.g. a 32k-native Qwen pushed to 128k uses `--rope-scale 4 --yarn-orig-ctx 32768 -c 131072`. Two caveats to remember:
- Applying YaRN scaling *below* the native context degrades short-context quality — only enable it when you genuinely need the longer window (hence Dynamic-YaRN exists).
- Extended context still costs KV-cache memory linearly, so on the 3060 this pairs directly with [[2026-05-29-kv-cache-quantization]] (quantize K/V to fit the longer window) — YaRN buys the *positions*, KV quant buys the *memory* to hold them.

## Source
- Paper: https://arxiv.org/abs/2309.00071 (Peng, Quesnelle, Fan, Shippole 2023)
- EleutherAI explainer: https://blog.eleuther.ai/yarn/
- llama.cpp implementation: PR #2268 (ggml-org/llama.cpp)

## Connected To
- [[2026-05-29-kv-cache-quantization]]
- [[2026-06-01-multi-head-latent-attention-mla]]
- [[2026-06-04-flash-attention-2-io-optimal-kernel]]
- [[2026-05-18-rtx3060-optimal-llm-models]]
