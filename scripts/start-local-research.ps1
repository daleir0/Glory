# Daily local research run (Tier 1: Gemma + Hermes).
# Skips gracefully if the local brain (proxy/LM Studio) isn't up.
$env:PATH = "C:\Users\dalei\AppData\Roaming\npm;" + $env:PATH

$date = Get-Date -Format "yyyy-MM-dd"
$log  = "E:\Glory\logs\local-research-$date.log"
New-Item -ItemType Directory -Force -Path "E:\Glory\logs" | Out-Null

# Health check: proxy must be serving Gemma
try {
    $null = Invoke-RestMethod -Uri "http://localhost:8082/v1/models" -TimeoutSec 8
} catch {
    "[$date] SKIP — proxy/LM Studio not running on 8082. Start LM Studio + proxy first." `
        | Out-File -FilePath $log -Encoding utf8
    exit 0
}

# Ensure Hermes endpoint is up (best-effort)
try { Invoke-RestMethod -Uri "http://localhost:8083/health" -TimeoutSec 4 | Out-Null }
catch { & "E:\Glory\scripts\start-hermes-endpoint.ps1"; Start-Sleep 3 }

"[$date] Starting local research..." | Out-File -FilePath $log -Encoding utf8
python "E:\Glory\scripts\local-research.py" *>> $log
"[$date] Done." | Out-File -FilePath $log -Encoding utf8 -Append
