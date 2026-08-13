# STAMP Start All Local Services — v1.0-P4
# Starts backend and frontend in separate windows

$ErrorActionPreference = "Stop"
$RootWarning = "[STAMPUP] Historical entry: use scripts/ops/stampup_restart.sh or scripts/ops/stampup_status.sh for the STAMPUP dev copy."
Write-Host $RootWarning -ForegroundColor Yellow
$RootDir = $PSScriptRoot | Split-Path -Parent
$LogDir = Join-Path $RootDir "logs_dev"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

Write-Host "[STAMP] Starting all local services..." -ForegroundColor Cyan

# Start backend in new window
$BackendScript = Join-Path $RootDir "start-backend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", "$BackendScript" -WindowStyle Normal

# Give backend time to initialize
Start-Sleep -Seconds 5

# Start frontend in new window
$FrontendScript = Join-Path $PSScriptRoot "start-frontend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", "$FrontendScript" -WindowStyle Normal

Write-Host "[STAMP] Services starting. Check console windows for status." -ForegroundColor Green
Write-Host "[STAMP] Backend:  http://localhost:12824/docs" -ForegroundColor Green
Write-Host "[STAMP] Frontend: http://localhost:12823" -ForegroundColor Green
