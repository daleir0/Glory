#!/bin/bash
# Glory Vault — Decrypt API key into environment.
# Firewall must pass before this runs. Never prints the key.

set -euo pipefail

VAULT_FILE="scripts/vault/glory.enc"

# Decrypt into environment variable only — never touch disk
ANTHROPIC_API_KEY=$(openssl enc -aes-256-cbc -d -pbkdf2 -iter 310000 \
    -in "$VAULT_FILE" \
    -pass pass:"${VAULT_KEY}" \
    -base64 2>/dev/null) \
    || { echo "[VAULT] Decryption failed — wrong key or corrupted file" >&2; exit 1; }

export ANTHROPIC_API_KEY

echo "[VAULT] Key loaded into environment."
