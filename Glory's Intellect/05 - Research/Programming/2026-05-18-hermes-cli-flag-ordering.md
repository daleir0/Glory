---
type: research-note
domain: Programming
confidence: verified
source: "Hermes CLI testing — observation 1415, session May 17 2026"
date: 2026-05-18
tags: [hermes, cli, flags, gotcha, debugging]
---
# Hermes CLI: The -z PROMPT Flag Must Come Before the Subcommand

## What

In the Hermes CLI, the `-z PROMPT` flag (used to pass a zero-shot prompt) must be placed **before** the subcommand name, not after it. Placing it after the subcommand causes the flag to be ignored or produce an error.

Correct: `hermes -z "my prompt" chat`
Wrong: `hermes chat -z "my prompt"`

## Why It Matters

This is a non-obvious CLI gotcha. If Hermes seems to be ignoring your prompt or behaving unexpectedly, check flag ordering first. Most CLIs accept flags anywhere; Hermes does not for this flag.

## Source

Direct CLI testing, May 17 2026. Observation 1415.

## Connected To

- [[05 - Research/AI/2026-05-18-hermes-lmstudio-provider-alias]]
