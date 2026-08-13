# STAMP Frontend Startup — v1.0-P4
$ErrorActionPreference = "Stop"
$RootDir = $PSScriptRoot | Split-Path -Parent
Set-Location $RootDir

Write-Host "[STAMP] Starting frontend dev server..." -ForegroundColor Cyan

if (-not (Test-Path "node_modules")) {
    Write-Host "[STAMP] Installing npm dependencies..." -ForegroundColor Yellow
    npm install
}

Write-Host "[STAMP] Frontend starting at http://localhost:12823" -ForegroundColor Green
npm run dev
