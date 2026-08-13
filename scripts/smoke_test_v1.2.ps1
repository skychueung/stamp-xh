# STAMP v1.2-lab-production-fast — Smoke Test Script (PowerShell)
# Run from project root: .\scripts\smoke_test_v1.2.ps1

$ErrorActionPreference = "Stop"
$API_BASE = $env:STAMP_API_URL ? $env:STAMP_API_URL : "http://localhost:8000/api"
$PASS = 0
$FAIL = 0

function Test-Endpoint {
    param([string]$Name, [string]$Uri, [string]$Method = "GET", [hashtable]$Body = $null)
    try {
        $params = @{ Uri = $Uri; Method = $Method; UseBasicParsing = $true }
        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json -Depth 4)
            $params.ContentType = "application/json"
        }
        $resp = Invoke-RestMethod @params -ErrorAction Stop
        Write-Host "[PASS] $Name" -ForegroundColor Green
        $script:PASS++
        return $resp
    } catch {
        $code = $_.Exception.Response ? $_.Exception.Response.StatusCode.value__ : "ERR"
        Write-Host "[FAIL] $Name (HTTP $code)" -ForegroundColor Red
        $script:FAIL++
        return $null
    }
}

Write-Host "=== STAMP v1.2 Smoke Test ===" -ForegroundColor Cyan
Write-Host "API Base: $API_BASE" -ForegroundColor Gray

# 1. Backend pytest
Write-Host "`n--- Backend Tests ---" -ForegroundColor Yellow
$pytest = python -m pytest backend/tests -q --tb=no 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[PASS] pytest suite" -ForegroundColor Green; $PASS++
} else {
    Write-Host "[FAIL] pytest suite" -ForegroundColor Red; $FAIL++
}

# 2. Frontend build
Write-Host "`n--- Frontend Build ---" -ForegroundColor Yellow
$build = npm run build 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[PASS] npm run build" -ForegroundColor Green; $PASS++
} else {
    Write-Host "[FAIL] npm run build" -ForegroundColor Red; $FAIL++
}

# 3. Docker compose config
Write-Host "`n--- Docker Config ---" -ForegroundColor Yellow
$docker = docker-compose -f docker-compose.v1.2.yml config 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[PASS] docker-compose config" -ForegroundColor Green; $PASS++
} else {
    Write-Host "[FAIL] docker-compose config (optional)" -ForegroundColor DarkYellow
}

# 4. Health endpoints
Write-Host "`n--- Health Endpoints ---" -ForegroundColor Yellow
Test-Endpoint "GET /health" "$API_BASE/health"
Test-Endpoint "GET /health/db" "$API_BASE/health/db"
Test-Endpoint "GET /health/storage" "$API_BASE/health/storage"
Test-Endpoint "GET /health/queue" "$API_BASE/health/queue"

# 5. LIMS/ELN smoke
Write-Host "`n--- LIMS/ELN Smoke ---" -ForegroundColor Yellow
$limsCreate = Test-Endpoint "POST /integrations" "$API_BASE/integrations" "POST" @{
    integration_type = "LIMS"
    name = "Smoke Test LIMS"
    base_url = "http://localhost:59999"
    auth_mode = "token"
}
if ($limsCreate) {
    $cfgId = $limsCreate.id
    Test-Endpoint "GET /integrations/$cfgId" "$API_BASE/integrations/$cfgId"
    Test-Endpoint "POST /integrations/$cfgId/test-sync" "$API_BASE/integrations/$cfgId/test-sync" "POST"
    # clean up
    Invoke-RestMethod -Uri "$API_BASE/integrations/$cfgId" -Method DELETE -UseBasicParsing -ErrorAction SilentlyContinue | Out-Null
}

# 6. Production MD smoke
Write-Host "`n--- Production MD Smoke ---" -ForegroundColor Yellow
Test-Endpoint "GET /production-md/durations" "$API_BASE/production-md/durations"
$mdCreate = Test-Endpoint "POST /production-md/jobs" "$API_BASE/production-md/jobs" "POST" @{
    project_id = "smoke-proj"
    candidate_id = "smoke-cand"
    duration_ns = 1
    topology_path = "/data/topol.tpr"
    coordinates_path = "/data/conf.gro"
}

# Summary
Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "Passed: $PASS" -ForegroundColor Green
Write-Host "Failed: $FAIL" -ForegroundColor Red
if ($FAIL -eq 0) {
    Write-Host "All smoke tests passed." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some smoke tests failed." -ForegroundColor Red
    exit 1
}
