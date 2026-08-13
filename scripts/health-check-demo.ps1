# STAMP Demo Health Check — v1.0-P4
# Lightweight check for demo readiness

$ErrorActionPreference = "SilentlyContinue"
Write-Host "[STAMP] Demo health check..." -ForegroundColor Cyan

$allOk = $true

# Backend
$backend = Invoke-WebRequest -Uri "http://localhost:12824/api/v1/health" -TimeoutSec 3 -UseBasicParsing
if ($backend.StatusCode -eq 200) {
    Write-Host "✅ Backend" -ForegroundColor Green
} else {
    Write-Host "❌ Backend" -ForegroundColor Red
    $allOk = $false
}

# Frontend
$frontend = Invoke-WebRequest -Uri "http://localhost:12823" -TimeoutSec 3 -UseBasicParsing
if ($frontend.StatusCode -eq 200) {
    Write-Host "✅ Frontend" -ForegroundColor Green
} else {
    Write-Host "❌ Frontend" -ForegroundColor Red
    $allOk = $false
}

# DB
$DbPath = Join-Path (Join-Path ($PSScriptRoot | Split-Path -Parent) "data_dev") "db\stamp_dev.db"
if (Test-Path $DbPath) {
    Write-Host "✅ Database" -ForegroundColor Green
} else {
    Write-Host "⚠️ Database not initialized" -ForegroundColor Yellow
    $allOk = $false
}

if ($allOk) {
    Write-Host "`n[STAMP] Demo is READY ✅" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n[STAMP] Demo NOT ready ❌" -ForegroundColor Red
    exit 1
}
