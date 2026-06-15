# Push current source snapshot to GitHub.
# Works around large binary files in local git history by building a clean
# tree in a temp directory. Local history is never touched.

param([string]$Message = "sync: Glory vault $(Get-Date -Format 'yyyy-MM-dd')")

$env:PATH = "C:\Users\dalei\AppData\Roaming\npm;" + $env:PATH + ";C:\Program Files\nodejs"

$root    = "E:\Glory"
$tmpDir  = "$env:TEMP\glory-gh-push-$(Get-Random)"
$token   = "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"
$remote  = "https://losinglory:$token@github.com/losinglory/Glory.git"

try {
    # Init a fresh repo in temp dir
    New-Item -ItemType Directory -Path $tmpDir | Out-Null
    git -C $tmpDir init -b main 2>&1 | Out-Null
    git -C $tmpDir config user.email "glory@research.session"
    git -C $tmpDir config user.name "Glory"
    git -C $tmpDir remote add origin $remote

    # Copy source files (no app binaries, no git objects, no node_modules)
    $excludes = @("Antigravity", "Qwen", "LM Studio", ".git", "node_modules", "autoresearch", "claude-mem-12.1.0")
    Get-ChildItem -Path $root -Force | Where-Object { $excludes -notcontains $_.Name } | ForEach-Object {
        $dest = Join-Path $tmpDir $_.Name
        if ($_.PSIsContainer) {
            Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
        } else {
            Copy-Item -Path $_.FullName -Destination $dest -Force
        }
    }

    # Commit and force push
    git -C $tmpDir add -A 2>&1 | Out-Null
    git -C $tmpDir commit -m $Message 2>&1 | Out-Null
    $pushOutput = git -C $tmpDir push --force origin main 2>&1
    Write-Output $pushOutput
    Write-Output "Pushed to GitHub: $Message"

} finally {
    Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}
