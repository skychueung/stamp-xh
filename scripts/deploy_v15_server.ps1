#Requires -Version 5.1
<#
.SYNOPSIS
    STAMP v1.5 P1.1 — Standardized SSH stamp218 Auto-Deploy Script

.DESCRIPTION
    Archives the current local git HEAD, uploads it to stamp218 via scp,
    extracts it safely (preserving data/), restarts only the backend on
    port 8001, and runs health / flexpepdock / queue verification.

.NOTES
    - Requires `ssh stamp218` to be configured in Windows SSH config.
    - Requires git in PATH.
    - Will NOT touch ports 8080, labelu, ws_worker, Dify, MinerU, VSCode server.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = git rev-parse --show-toplevel 2>$null
if ($RepoRoot -and $RepoRoot -like "*stamp-targeted-peptide-platform-target-design-dev*") {
    Write-Warn "Formal deploy script is disabled in the stampup dev copy."
    Write-Warn "Use the dev-copy startup and healthcheck scripts under scripts/ops instead."
    exit 1
}

# ─── Configuration ───────────────────────────────────────────────────────────
$ServerHost      = "stamp218"
$ServerUser      = "xh"
$RemoteProject   = "/home/xh/stamp"
$RemoteBackend   = "$RemoteProject/backend"
$RemoteData      = "$RemoteProject/data"
$ArchiveName     = "stamp-deploy-v15.zip"
$LocalArchive    = "$env:TEMP\$ArchiveName"
$RemoteArchive   = "/tmp/$ArchiveName"
$BackupDirBase   = "/home/xh/backups"

# ─── Helpers ─────────────────────────────────────────────────────────────────
function Write-Header($msg) { Write-Host "`n[DEPLOY] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "[DEPLOY] ✅ $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[DEPLOY] ⚠️  $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[DEPLOY] ❌ $msg" -ForegroundColor Red }

function Invoke-Ssh($cmd) {
    $output = ssh $ServerHost "$cmd" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "SSH command failed (exit $LASTEXITCODE): $cmd`n$output"
    }
    return $output
}

function Invoke-Curl($url) {
    $json = Invoke-Ssh "curl -s -m 10 $url"
    try {
        return $json | ConvertFrom-Json
    } catch {
        throw "Invalid JSON from $url : $json"
    }
}

# ─── Phase 0 — Validate local repo ───────────────────────────────────────────
Write-Header "Validating local git repository..."
$gitRoot = git rev-parse --show-toplevel 2>$null
if (-not $gitRoot) {
    Write-Err "Not inside a git repository. Aborting."
    exit 1
}
Set-Location $gitRoot

$branch = git branch --show-current
Write-Ok "Local repo: $gitRoot | Branch: $branch"

# ─── Phase 1 — Archive ───────────────────────────────────────────────────────
Write-Header "Archiving current HEAD ($branch)..."
if (Test-Path $LocalArchive) { Remove-Item $LocalArchive -Force }
git archive HEAD -o "$LocalArchive"
if (-not (Test-Path $LocalArchive)) {
    Write-Err "git archive failed — $LocalArchive not created."
    exit 1
}
$archiveSize = (Get-Item $LocalArchive).Length
Write-Ok "Archive created: $LocalArchive ($archiveSize bytes)"

# ─── Phase 2 — Upload ────────────────────────────────────────────────────────
Write-Header "Uploading archive to $ServerHost..."
scp "$LocalArchive" "${ServerHost}:${RemoteArchive}"
Write-Ok "Upload complete"

# ─── Phase 3 — Deploy on server ──────────────────────────────────────────────
Write-Header "Deploying on $ServerHost..."

$timestamp = Invoke-Ssh "date +%s"
$backupPath = "$BackupDirBase/stamp-targeted-peptide-platform-${timestamp}"

$deployScript = @"
set -e
echo '>>> Creating backup at $backupPath'
mkdir -p $BackupDirBase
cp -a "$RemoteProject" "$backupPath"
echo '>>> Backup done'

echo '>>> Preserving data directory'
if [ -d "$RemoteData" ]; then
    mv "$RemoteData" "/tmp/data.bak.${timestamp}"
else
    echo '>>> No data dir found, skipping backup'
fi

echo '>>> Extracting archive'
cd "$RemoteProject"
unzip -o "$RemoteArchive"

echo '>>> Restoring data directory'
if [ -d "/tmp/data.bak.${timestamp}" ]; then
    mv "/tmp/data.bak.${timestamp}" "$RemoteData"
fi

echo '>>> Cleaning up remote archive'
rm -f "$RemoteArchive"

echo '>>> Deploy complete'
"@

Invoke-Ssh "$deployScript"
Write-Ok "Server deploy complete (backup: $backupPath)"

# ─── Phase 4 — Restart backend (port 8001 only) ──────────────────────────────
Write-Header "Restarting backend on port 8001..."

$restartScript = @"
set -e
# Find and kill ONLY the uvicorn on port 8001
echo '>>> Stopping uvicorn on port 8001'
PID=\$(ss -tlnp 2>/dev/null | grep 8001 | grep -oP 'pid=\K[0-9]+' | head -n1)
if [ -n "\$PID" ]; then
    kill -9 \$PID || true
    sleep 1
    echo ">>> Killed PID \$PID"
else
    echo '>>> No uvicorn on 8001 found'
fi

# Also try pkill as fallback (narrow match)
pkill -f 'uvicorn app.main:app --host 0.0.0.0 --port 8001' || true
sleep 1

echo '>>> Starting uvicorn'
cd "$RemoteBackend"
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > "$RemoteProject/uvicorn.log" 2>&1 &
echo ">>> New PID: \$!"
sleep 3
"@

Invoke-Ssh "$restartScript"
Write-Ok "Backend restarted on port 8001"

# ─── Phase 5 — Verification ──────────────────────────────────────────────────
Write-Header "Running verification checks..."

# 5a — Health
$health = Invoke-Curl "http://127.0.0.1:8001/api/health"
if ($health.code -eq 200 -and $health.data.status -eq "healthy") {
    Write-Ok "Health check PASS"
} else {
    Write-Err "Health check FAIL: $($health | ConvertTo-Json -Depth 3)"
    exit 1
}

# 5b — FlexPepDock probe
$probe = Invoke-Curl "http://127.0.0.1:8001/api/v1/flexpepdock-pilot/probe"
if ($probe.code -eq 200 -and $probe.data.status -eq "AVAILABLE") {
    Write-Ok "FlexPepDock probe PASS"
} else {
    Write-Err "FlexPepDock probe FAIL: $($probe | ConvertTo-Json -Depth 3)"
    exit 1
}

# 5c — Queue health
$queue = Invoke-Curl "http://127.0.0.1:8001/api/health/queue"
if ($queue.code -eq 200 -and $queue.data.status -eq "healthy") {
    Write-Ok "Queue health PASS"
} else {
    Write-Err "Queue health FAIL: $($queue | ConvertTo-Json -Depth 3)"
    exit 1
}

# 5d — Backend CWD
$cwd = Invoke-Ssh "readlink -f /proc/\$(ss -tlnp | grep 8001 | grep -oP 'pid=\K[0-9]+' | head -n1)/cwd"
if ($cwd -eq "$RemoteBackend") {
    Write-Ok "Backend CWD correct: $cwd"
} else {
    Write-Warn "Backend CWD mismatch: $cwd (expected $RemoteBackend)"
}

# 5e — Other services untouched
Write-Header "Confirming other services are untouched..."
$services = @(
    @{ Port = 8080; Name = "frontend" },
    @{ Port = 8001; Name = "backend (should be ours)" }
)

foreach ($svc in $services) {
    $p = $svc.Port
    $result = Invoke-Ssh "ss -tlnp 2>/dev/null | grep ':$p ' || echo 'NOT_LISTENING'"
    if ($result -eq "NOT_LISTENING") {
        Write-Warn "Port $p ($($svc.Name)) not listening"
    } else {
        Write-Ok "Port $p ($($svc.Name)) still active"
    }
}

# ─── Phase 6 — Summary ─────────────────────────────────────────────────────────
Write-Header "Deployment Summary"
Write-Ok "Branch deployed : $branch"
Write-Ok "Server          : $ServerHost ($RemoteProject)"
Write-Ok "Backup path     : $backupPath"
Write-Ok "Health          : $($health.code) — $($health.message)"
Write-Ok "FlexPepDock     : $($probe.data.status)"
Write-Ok "Queue           : $($queue.data.status) — total_jobs=$($queue.data.total_jobs)"

Write-Host "`n[DEPLOY] 🎉 All checks passed. Deployment successful." -ForegroundColor Green
