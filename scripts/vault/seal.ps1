# Glory Vault Sealer
# Run this locally to encrypt your Anthropic API key into the vault.
# Usage: .\seal.ps1
# You will be prompted for your API key and vault passphrase.
# The encrypted output is written to scripts/vault/glory.enc

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Glory Vault — Key Sealing"
Write-Host "--------------------------"
Write-Host ""

$apiKey    = Read-Host "Enter your Anthropic API key (sk-ant-...)" -AsSecureString
$vaultKey  = Read-Host "Enter vault passphrase (this goes in GitHub Secrets as VAULT_KEY)" -AsSecureString

# Convert SecureString to plain text for openssl
$apiKeyPlain   = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey))
$vaultKeyPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($vaultKey))

$outFile = "E:\Glory\scripts\vault\glory.enc"

# Encrypt with AES-256-CBC, 310000 PBKDF2 iterations, base64 output
$apiKeyPlain | openssl enc -aes-256-cbc -pbkdf2 -iter 310000 -salt `
    -pass "pass:$vaultKeyPlain" -out $outFile -base64

# Clear plaintext from memory
$apiKeyPlain   = $null
$vaultKeyPlain = $null
[System.GC]::Collect()

Write-Host ""
Write-Host "Sealed: $outFile"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. git add scripts/vault/glory.enc && git commit -m 'vault: seal API key'"
Write-Host "  2. Run .\scripts\push-to-github.ps1 to sync"
Write-Host "  3. Add VAULT_KEY to GitHub Secrets:"
Write-Host "     github.com/losinglory/Glory/settings/secrets/actions"
Write-Host ""
