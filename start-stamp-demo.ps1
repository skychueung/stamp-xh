# STAMP Start Demo — v1.0-P4
# One-command demo startup

$ErrorActionPreference = "Stop"
$RootWarning = "[STAMPUP] Historical entry: STAMPUP dev copy should use scripts/ops/stampup_* instead of demo startup."
Write-Host $RootWarning -ForegroundColor Yellow
$RootDir = $PSScriptRoot | Split-Path -Parent
$LogDir = Join-Path $RootDir "logs_dev"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

Write-Host "[STAMP] Starting STAMP demo environment..." -ForegroundColor Cyan

# Start backend
$BackendScript = Join-Path $RootDir "start-backend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", "$BackendScript" -WindowStyle Normal
Start-Sleep -Seconds 6

# Start frontend
$FrontendScript = Join-Path $PSScriptRoot "start-frontend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", "$FrontendScript" -WindowStyle Normal
Start-Sleep -Seconds 3

Write-Host "[STAMP] Demo started!" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:12824/docs" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:12823" -ForegroundColor Green
Write-Host "`nTo stop: .\scripts\stop-demo-services.ps1" -ForegroundColor Yellow
