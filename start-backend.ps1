# STAMP Backend Startup — v1.0-P4
$ErrorActionPreference = "Stop"
$RootWarning = "[STAMPUP] Historical entry: use scripts/ops/stampup_start_backend.sh for the STAMPUP dev copy."
Write-Host $RootWarning -ForegroundColor Yellow
$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$LogDir = Join-Path $RootDir "logs_dev"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

$DataRoot = Join-Path $RootDir "data_dev"
$DataDbDir = Join-Path $DataRoot "db"
foreach ($dir in @(
    $DataRoot,
    (Join-Path $DataRoot "artifacts"),
    (Join-Path $DataRoot "uploads"),
    (Join-Path $DataRoot "jobs"),
    $DataDbDir,
    (Join-Path $RootDir "models_dev"),
    (Join-Path $RootDir "reports")
)) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
}

$DbPath = Join-Path $DataDbDir "stamp_dev.db"
$env:STAMP_DATA_DIR = $DataRoot
$env:STAMP_BATCH_JOBS_DIR = (Join-Path $DataRoot "jobs")
$env:STAMP_DATABASE_URL = "sqlite:///" + (($DbPath -replace '\\', '/'))
$env:STAMP_DIST_DIR = (Join-Path $RootDir "dist")

Write-Host "[STAMP] Starting backend..." -ForegroundColor Cyan
Set-Location $BackendDir

if (-not (Test-Path "venv")) {
    Write-Host "[STAMP] Creating venv..." -ForegroundColor Yellow
    python -m venv venv
}
& (Join-Path (Join-Path (Join-Path $BackendDir "venv") "Scripts") "Activate.ps1")
pip install -q -r requirements.txt

if (-not (Test-Path $DbPath)) {
    Write-Host "[STAMP] Initializing DB..." -ForegroundColor Yellow
    python -c "from app.database import init_db; init_db()"
}

# Log PID for safe shutdown
$PidFile = Join-Path $LogDir "backend.pid"
$LogFile = Join-Path $LogDir "backend.log"

Write-Host "[STAMP] Backend at http://localhost:12824" -ForegroundColor Green
Write-Host "[STAMP] Logs: $LogFile" -ForegroundColor Gray

# Start uvicorn and capture PID
$proc = Start-Process -FilePath "uvicorn" -ArgumentList "main:app","--reload","--host","0.0.0.0","--port","12824" -PassThru -RedirectStandardOutput $LogFile -RedirectStandardError (Join-Path $LogDir "backend.err")
$proc.Id | Out-File -FilePath $PidFile -Encoding utf8

Write-Host "[STAMP] Backend PID: $($proc.Id)" -ForegroundColor Gray
