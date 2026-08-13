# STAMP Health Check — v1.0-P4
$ErrorActionPreference = "SilentlyContinue"
$RootDir = $PSScriptRoot | Split-Path -Parent

Write-Host "[STAMP] Running health checks..." -ForegroundColor Cyan
Write-Host ""

# 1. Backend health
Write-Host "--- Backend Health ---" -ForegroundColor Yellow
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:12824/api/v1/health" -TimeoutSec 5 -UseBasicParsing
    if ($resp.StatusCode -eq 200) {
        Write-Host "✅ Backend: http://localhost:12824 — OK" -ForegroundColor Green
        $body = $resp.Content | ConvertFrom-Json
        Write-Host "   Status: $($body.status)" -ForegroundColor Gray
    } else {
        Write-Host "⚠️ Backend: HTTP $($resp.StatusCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Backend: Not reachable at http://localhost:12824" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Gray
}
Write-Host ""

# 2. Frontend
Write-Host "--- Frontend URL ---" -ForegroundColor Yellow
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:12823" -TimeoutSec 5 -UseBasicParsing
    if ($resp.StatusCode -eq 200) {
        Write-Host "✅ Frontend: http://localhost:12823 — OK" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Frontend: HTTP $($resp.StatusCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Frontend: Not reachable at http://localhost:12823" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Gray
}
Write-Host ""

# 3. Demo dataset
Write-Host "--- Demo Dataset ---" -ForegroundColor Yellow
$DemoPath = Join-Path $RootDir "backend\tests\fixtures\v1.0_demo_dataset.json"
if (Test-Path $DemoPath) {
    Write-Host "✅ Demo dataset found: $DemoPath" -ForegroundColor Green
} else {
    Write-Host "❌ Demo dataset missing" -ForegroundColor Red
}
Write-Host ""

# 4. Database
Write-Host "--- Database ---" -ForegroundColor Yellow
$DbPath = Join-Path (Join-Path $RootDir "data_dev") "db\stamp_dev.db"
if (Test-Path $DbPath) {
    $size = (Get-Item $DbPath).Length
    Write-Host "✅ Database found: $DbPath ($size bytes)" -ForegroundColor Green
} else {
    Write-Host "⚠️ Database not initialized yet" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "[STAMP] Health check complete." -ForegroundColor Cyan
