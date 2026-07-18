---
type: research-note
domain: AI
confidence: verified
source: "https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md"
date: 2026-07-17
tags: [sampling, inference, llama-cpp, repetition, decoding, local-inference]
---
# DRY (Don't Repeat Yourself) — a multi-token repetition sampler that kills degenerate loops

## What
DRY is a sampling-time repetition penalty (introduced 2024 by p-e-w, now built into llama.cpp) that penalizes tokens which would **extend a multi-token sequence already present in the context**, rather than penalizing individual tokens like the classic `repetition_penalty`. When the token about to be sampled would continue a repeated n-gram, its logit is reduced by an **exponentially escalating** penalty:

```
penalty = dry_multiplier * dry_base ^ (match_length - dry_allowed_length)
```

where `match_length` is the length of the longest suffix of the current output that matches an earlier span. Repeats of length ≤ `dry_allowed_length` are ignored entirely, so natural short phrases ("of the", "in a") pass untouched, while a verbatim loop gets punished harder the longer it runs.

Defaults / knobs (llama.cpp): `dry_multiplier` = 0.0 (**disabled**; start ~0.8), `dry_base` = 1.75, `dry_allowed_length` = 2, `dry_penalty_last_n` = -1 (scan the whole context — recommended for loop detection), `dry_sequence_breakers` = `['\n', ':', '"', '*']`. Sequence breakers reset the matcher so repetition tracking doesn't bleed across structural boundaries (new lines, quotes, list markers).

## Why It Matters
Degenerate repetition — a local model falling into a verbatim loop or restating the same clause — is one of the most common failure modes on Glory's llama.cpp stack (Gemma, Qwen3, Kimi), and it gets worse at low temperature and long context, exactly where an agentic loop lives. Classic `repetition_penalty` fights this by nuking *any* reuse of a token, which degrades coherence (it also penalizes necessary words). DRY is surgical: it only strikes when an actual multi-token sequence is repeating, so it can crush loops **without** damaging normal prose or code that legitimately reuses identifiers. It composes cleanly with the truncation samplers already in the vault — DRY (repetition control) runs alongside min-p / top-n-sigma / XTC (tail shaping), not instead of them. Practical lever: `--dry-multiplier 0.8 --dry-base 1.75 --dry-allowed-length 2` in `llama-server`, tuning multiplier up if loops persist. For long-running Glory agent sessions this is close to free insurance against the model wedging on a repeated token.

## Source
- llama.cpp server sampling params: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- LLM Sampling Parameters Guide (smcleod.net, 2025): https://smcleod.net/2025/04/llm-sampling-parameters-guide/
- Original design: p-e-w, "DRY" repetition penalty (text-generation-webui PR, 2024)

## Connected To
- [[2026-07-13-xtc-exclude-top-choices-sampler]]
- [[2026-07-09-top-n-sigma-sampling]]
- [[2026-06-28-min-p-sampling]]
- [[2026-07-03-streamingllm-attention-sinks]]
