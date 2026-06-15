#!/bin/bash
# Glory Vault Firewall
# Validates execution environment before any decryption is attempted.
# All checks must pass. One failure = hard exit.

set -euo pipefail

ALLOWED_REPO="losinglory/Glory"
ALLOWED_BRANCH="main"
ALLOWED_RUNNER="ubuntu"

fail() {
    echo "[VAULT FIREWALL] DENIED: $1" >&2
    exit 1
}

# Rule 1: Must be running inside GitHub Actions
[[ "${GITHUB_ACTIONS:-}" == "true" ]] || fail "Not a GitHub Actions environment"

# Rule 2: Must be the correct repository
[[ "${GITHUB_REPOSITORY:-}" == "$ALLOWED_REPO" ]] || fail "Repository mismatch: ${GITHUB_REPOSITORY:-unknown}"

# Rule 3: Must be on the correct branch
[[ "${GITHUB_REF:-}" == "refs/heads/$ALLOWED_BRANCH" ]] || fail "Branch mismatch: ${GITHUB_REF:-unknown}"

# Rule 4: Must be triggered by schedule or manual dispatch (not a PR from a fork)
[[ "${GITHUB_EVENT_NAME:-}" == "schedule" || "${GITHUB_EVENT_NAME:-}" == "workflow_dispatch" ]] \
    || fail "Trigger not allowed: ${GITHUB_EVENT_NAME:-unknown}"

# Rule 5: Actor must be the repo owner or GitHub Actions bot
[[ "${GITHUB_ACTOR:-}" == "losinglory" || "${GITHUB_ACTOR:-}" == "github-actions[bot]" ]] \
    || fail "Actor not permitted: ${GITHUB_ACTOR:-unknown}"

# Rule 6: Vault key must be present
[[ -n "${VAULT_KEY:-}" ]] || fail "VAULT_KEY not set"

# Rule 7: Encrypted key file must exist and be non-empty
[[ -s "scripts/vault/glory.enc" ]] || fail "Encrypted key file missing or empty"

echo "[VAULT FIREWALL] All checks passed."
