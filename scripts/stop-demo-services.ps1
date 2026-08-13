# STAMP Stop Demo Services — v1.0-P4
# Safely stops only STAMP-related processes, NOT all Python.

$ErrorActionPreference = "SilentlyContinue"
Write-Host "[STAMP] Stopping demo services..." -ForegroundColor Cyan

# Find uvicorn processes (backend)
$uvicorn = Get-Process -Name "python" | Where-Object {
    $_.CommandLine -like "*uvicorn*main:app*" 2>$null
}
if ($uvicorn) {
    $uvicorn | Stop-Process -Force
    Write-Host "✅ Backend (uvicorn) stopped" -ForegroundColor Green
} else {
    Write-Host "ℹ️ Backend (uvicorn) not running" -ForegroundColor Gray
}

# Find vite processes (frontend dev server)
$vite = Get-Process -Name "node" | Where-Object {
    $_.CommandLine -like "*vite*" 2>$null
}
if ($vite) {
    $vite | Stop-Process -Force
    Write-Host "✅ Frontend (vite) stopped" -ForegroundColor Green
} else {
    Write-Host "ℹ️ Frontend (vite) not running" -ForegroundColor Gray
}

Write-Host "[STAMP] Done." -ForegroundColor Cyan
