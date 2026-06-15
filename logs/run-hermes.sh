#!/bin/bash
# Daily Hermes invocation — avoids inline-quoting traps.
HERMES="$HOME/.local/bin/hermes"
PROMPT_FILE="/mnt/e/Glory/logs/hermes-daily-prompt.txt"

cd "$HOME/hermes-agent/hermes-agent-2026.4.30" 2>/dev/null || true

if [ ! -x "$HERMES" ]; then
    echo "HERMES_NOT_FOUND"
    exit 1
fi

PROMPT="$(cat "$PROMPT_FILE")"
timeout 150 "$HERMES" -z "$PROMPT" 2>&1
