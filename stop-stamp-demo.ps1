# STAMP Stop Demo — v1.0-P4
# Alias for stop-demo-services.ps1

$RootWarning = "[STAMPUP] Historical entry: use scripts/ops/stampup_stop.sh for the STAMPUP dev copy."
Write-Host $RootWarning -ForegroundColor Yellow
$ScriptDir = $PSScriptRoot
& (Join-Path $ScriptDir "stop-demo-services.ps1")
