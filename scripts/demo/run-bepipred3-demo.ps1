<#
.SYNOPSIS
    BepiPred3 Demo Script — One-click epitope prediction workflow for STAMP platform.

.DESCRIPTION
    This script automates the full BepiPred3 workflow:
    1. Check sidecar health
    2. Check STAMP backend health
    3. Create a demo project
    4. Create a bepipred3_scan job
    5. Start the job asynchronously
    6. Poll until completion / failure / timeout
    7. Persist results
    8. Query candidates
    9. Output report and frontend URL

.NOTES
    - Requires PowerShell 7+
    - Sidecar must be running at http://127.0.0.1:8010
    - STAMP backend must be running at http://127.0.0.1:8000
    - No candidates are fabricated; candidate_count=0 is a valid outcome.
    - This demo does NOT produce MIC, MBC, hemolysis, toxicity, ipTM, pDockQ, ΔG, or docking scores.
#>

param(
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [string]$SidecarUrl = "http://127.0.0.1:8010",
    [string]$FrontendUrl = "http://127.0.0.1:3000",
    [int]$PollIntervalSec = 5,
    [int]$MaxPollAttempts = 60,
    [string]$ReportDir = "",
    [switch]$UseSyncRun,
    [switch]$SkipHealthChecks
)

# ── Configuration ───────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
$script:StartTime = Get-Date
$script:LogLines = [System.Collections.Generic.List[string]]::new()

function Write-Log {
    param([string]$Level, [string]$Message)
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$ts] [$Level] $Message"
    $script:LogLines.Add($line)
    switch ($Level) {
        "ERROR"   { Write-Host $line -ForegroundColor Red }
        "WARN"    { Write-Host $line -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $line -ForegroundColor Green }
        default   { Write-Host $line }
    }
}

function Write-Info  { param([string]$m) Write-Log "INFO"  $m }
function Write-Warn  { param([string]$m) Write-Log "WARN"  $m }
function Write-ErrorLog { param([string]$m) Write-Log "ERROR" $m }
function Write-Ok    { param([string]$m) Write-Log "SUCCESS" $m }

# ── Report path ─────────────────────────────────────────────────────────────
if ([string]::IsNullOrWhiteSpace($ReportDir)) {
    $ReportDir = Join-Path $PSScriptRoot ".." ".." ".." ".." ".." "ai" "product" "kimi" "agent-bridge" "reports"
    $ReportDir = [System.IO.Path]::GetFullPath($ReportDir)
}
if (-not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
}
$ReportPath = Join-Path $ReportDir "V010_P2E_BEPIPRED3_DEMO_RUN_REPORT.md"

# ── Health Checks ───────────────────────────────────────────────────────────
if (-not $SkipHealthChecks) {
    Write-Info "Checking BepiPred3 sidecar at $SidecarUrl/api/health ..."
    try {
        $sidecarHealth = Invoke-RestMethod -Uri "$SidecarUrl/api/health" -TimeoutSec 10
        Write-Ok "Sidecar health OK: $($sidecarHealth | ConvertTo-Json -Compress)"
    } catch {
        Write-ErrorLog "Sidecar NOT RUNNING at $SidecarUrl/api/health"
        Write-ErrorLog "Please start sidecar first:"
        Write-ErrorLog "  D:\ai\tool\skill\bepipred3-api\start-bepipred3-sidecar.ps1 -Warmup"
        throw "Sidecar health check failed"
    }

    Write-Info "Checking STAMP backend at $BackendUrl/api/v1/health ..."
    try {
        $backendHealth = Invoke-RestMethod -Uri "$BackendUrl/health" -TimeoutSec 10
        Write-Ok "Backend health OK: $($backendHealth | ConvertTo-Json -Compress)"
    } catch {
        Write-ErrorLog "Backend NOT RUNNING at $BackendUrl/health"
        Write-ErrorLog "Please start backend first:"
        Write-ErrorLog "  cd D:\Desktop\靶向肽\github\前端\backend"
        Write-ErrorLog "  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
        throw "Backend health check failed"
    }
} else {
    Write-Warn "Health checks skipped (--SkipHealthChecks)"
}

# ── Demo sequence: Bovine Serum Albumin (BSA) fragment ──────────────────────
# A real protein sequence, ~200 aa — moderate length for CPU inference.
$DemoSequence = "MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGEENFKALVLIAFAQYLQQCPFEDHVKLVNEVTEFAKTCVADESAENCDKSLHTLFGDKLCTVATLRETYGEMADCCAKQEPERNECFLQHKDDNPNLPRLVRPEVDVMCTAFHDNEETFLKKYLYEIARRHPYFYAPELLYYANKYNGVFQECCQAEDKGA"

# ── Step 1: Create Project ──────────────────────────────────────────────────
Write-Info "Step 1/8: Creating demo project ..."
$projectPayload = @{
    name = "BepiPred3 Demo — BSA Fragment"
    description = "Automated demo run for BepiPred3 epitope prediction workflow."
    species = "Bovine"
    project_type = "epitope_screening"
} | ConvertTo-Json -Depth 3

try {
    $project = Invoke-RestMethod -Uri "$BackendUrl/api/v1/projects" -Method POST -ContentType "application/json" -Body $projectPayload
    $projectId = $project.id
    if (-not $projectId) { $projectId = $project.data.id }
    Write-Ok "Project created: id=$projectId, name='$($project.name)'"
} catch {
    Write-ErrorLog "Failed to create project: $($_.Exception.Message)"
    throw
}

# ── Step 2: Create Job ──────────────────────────────────────────────────────
Write-Info "Step 2/8: Creating bepipred3_scan job ..."
$jobPayload = @{
    project_id = $projectId
    job_type = "bepipred3_scan"
    input_json = @{
        sequence = $DemoSequence
        min_length = 8
        max_length = 25
    }
} | ConvertTo-Json -Depth 5

try {
    $job = Invoke-RestMethod -Uri "$BackendUrl/api/v1/jobs" -Method POST -ContentType "application/json" -Body $jobPayload
    $jobId = $job.id
    if (-not $jobId) { $jobId = $job.data.id }
    Write-Ok "Job created: id=$jobId, status='$($job.status)'"
} catch {
    Write-ErrorLog "Failed to create job: $($_.Exception.Message)"
    throw
}

# ── Step 3: Start Job ───────────────────────────────────────────────────────
Write-Info "Step 3/8: Starting job asynchronously ..."
try {
    if ($UseSyncRun) {
        Write-Warn "Using synchronous /run (blocking) — not recommended for production"
        $startRes = Invoke-RestMethod -Uri "$BackendUrl/api/v1/jobs/$jobId/run" -Method POST
    } else {
        $startRes = Invoke-RestMethod -Uri "$BackendUrl/api/v1/jobs/$jobId/start" -Method POST
    }
    Write-Ok "Job start accepted: $($startRes | ConvertTo-Json -Compress)"
} catch {
    Write-ErrorLog "Failed to start job: $($_.Exception.Message)"
    throw
}

# ── Step 4: Poll ────────────────────────────────────────────────────────────
Write-Info "Step 4/8: Polling job status (interval=${PollIntervalSec}s, max=${MaxPollAttempts}) ..."
$finalStatus = $null
$attempt = 0
while ($attempt -lt $MaxPollAttempts) {
    Start-Sleep -Seconds $PollIntervalSec
    $attempt++
    try {
        $jobStatus = Invoke-RestMethod -Uri "$BackendUrl/api/v1/jobs/$jobId" -TimeoutSec 10
        $currentStatus = $jobStatus.status
        if (-not $currentStatus) { $currentStatus = $jobStatus.data.status }
        $progress = if ($jobStatus.progress -ne $null) { $jobStatus.progress } elseif ($jobStatus.data.progress -ne $null) { $jobStatus.data.progress } else { 0 }
        Write-Info "  Poll #$attempt — status='$currentStatus', progress=$progress%"
        if ($currentStatus -in @("succeeded", "failed", "cancelled")) {
            $finalStatus = $currentStatus
            break
        }
    } catch {
        Write-Warn "  Poll #$attempt failed: $($_.Exception.Message)"
    }
}

if (-not $finalStatus) {
    Write-ErrorLog "Job did not reach terminal status within timeout ($($MaxPollAttempts * $PollIntervalSec)s)"
    throw "Job polling timeout"
}

Write-Ok "Job terminal status: '$finalStatus'"

if ($finalStatus -eq "failed") {
    $errorMsg = if ($jobStatus.error_message) { $jobStatus.error_message } elseif ($jobStatus.data.error_message) { $jobStatus.data.error_message } else { "No error message" }
    Write-ErrorLog "Job failed: $errorMsg"
    throw "Job failed"
}

if ($finalStatus -eq "cancelled") {
    Write-ErrorLog "Job was cancelled by user or system."
    throw "Job cancelled"
}

# ── Step 5: Persist Results ─────────────────────────────────────────────────
Write-Info "Step 5/8: Persisting BepiPred3 results ..."
try {
    $persistRes = Invoke-RestMethod -Uri "$BackendUrl/api/v1/jobs/$jobId/persist-bepipred3-results" -Method POST -TimeoutSec 30
    Write-Ok "Persist succeeded: $($persistRes | ConvertTo-Json -Compress)"
} catch {
    Write-ErrorLog "Failed to persist results: $($_.Exception.Message)"
    throw
}

# ── Step 6: Get Scan ID ─────────────────────────────────────────────────────
Write-Info "Step 6/8: Retrieving scan_id from job output ..."
try {
    $jobFinal = Invoke-RestMethod -Uri "$BackendUrl/api/v1/jobs/$jobId" -TimeoutSec 10
    $outputJson = if ($jobFinal.output_json) { $jobFinal.output_json } elseif ($jobFinal.data.output_json) { $jobFinal.data.output_json } else { $null }
    $scanId = $null
    if ($outputJson -and $outputJson.scan_id) {
        $scanId = $outputJson.scan_id
    } elseif ($outputJson -and $outputJson.data -and $outputJson.data.scan_id) {
        $scanId = $outputJson.data.scan_id
    }
    if (-not $scanId) {
        Write-Warn "scan_id not found in job output_json. Attempting to query latest scan for project ..."
        $scans = Invoke-RestMethod -Uri "$BackendUrl/api/v1/epitope-scans?project_id=$projectId" -TimeoutSec 10
        if ($scans -and $scans.Count -gt 0) {
            $scanId = $scans[0].id
        }
    }
    if (-not $scanId) {
        throw "Could not determine scan_id"
    }
    Write-Ok "Scan ID: $scanId"
} catch {
    Write-ErrorLog "Failed to get scan_id: $($_.Exception.Message)"
    throw
}

# ── Step 7: Query Candidates ────────────────────────────────────────────────
Write-Info "Step 7/8: Querying epitope candidates ..."
try {
    $candidates = Invoke-RestMethod -Uri "$BackendUrl/api/v1/epitope-scans/$scanId/candidates" -TimeoutSec 10
    $candidateCount = if ($candidates -is [array]) { $candidates.Count } elseif ($candidates.data) { $candidates.data.Count } else { 0 }
    Write-Ok "Candidates retrieved: count=$candidateCount"
} catch {
    Write-ErrorLog "Failed to query candidates: $($_.Exception.Message)"
    throw
}

# ── Step 8: Output Report ───────────────────────────────────────────────────
Write-Info "Step 8/8: Generating demo report ..."
$duration = (Get-Date) - $script:StartTime

$reportContent = @"
# BepiPred3 Demo Run Report

- **Generated**: $((Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))
- **Duration**: $($duration.ToString("hh\:mm\:ss"))
- **Backend**: $BackendUrl
- **Sidecar**: $SidecarUrl
- **Frontend**: $FrontendUrl

---

## Execution Log

``````
$($script:LogLines -join "`n")
``````

---

## Results

| Field | Value |
|-------|-------|
| project_id | $projectId |
| job_id | $jobId |
| scan_id | $scanId |
| job_status | $finalStatus |
| candidate_count | $candidateCount |
| sequence_length | $($DemoSequence.Length) |

---

## Candidate Summary

"@

if ($candidateCount -eq 0) {
    $reportContent += @"
**BepiPred3 completed successfully but no candidate epitopes passed filters.**

No candidates were fabricated. A count of zero is a valid scientific outcome — it means the current filtering criteria (sequence length, binding threshold, etc.) did not yield any qualifying epitopes for this input sequence.

"@
} else {
    $reportContent += @"
Top candidates (up to 5 shown):

| # | Sequence | Score | Source |
|---|----------|-------|--------|
"@
    $top5 = if ($candidates -is [array]) { $candidates | Select-Object -First 5 } elseif ($candidates.data) { $candidates.data | Select-Object -First 5 } else { @() }
    $idx = 0
    foreach ($c in $top5) {
        $idx++
        $seq = if ($c.sequence) { $c.sequence } elseif ($c.peptide_sequence) { $c.peptide_sequence } else { "N/A" }
        $score = if ($c.ranking_score -ne $null) { $c.ranking_score } elseif ($c.score -ne $null) { $c.score } else { "N/A" }
        $source = if ($c.source) { $c.source } else { "bepipred3" }
        $reportContent += "| $idx | ``$seq`` | $score | $source |`n"
    }
    $reportContent += "`n"
}

$reportContent += @"
---

## Frontend URL

```
$FrontendUrl/epitope-screening?scan_id=$scanId
```

Open the above URL in your browser to view the epitope screening page.

---

## Scientific Boundary Notice

This demo uses **BepiPred3** for computational epitope prediction only.

- **Validation status**: NOT_EXPERIMENTALLY_VALIDATED
- **Prediction status**: COMPUTATIONAL_PREDICTION_ONLY
- **Does NOT include**: MIC, MBC, hemolysis, toxicity, ipTM, pDockQ, ΔG, docking_score
- **Not a substitute for**: wet-lab validation, animal studies, or clinical trials

---

## Sign-off

- **Script**: run-bepipred3-demo.ps1
- **Status**: ✅ Demo completed
"@

$reportContent | Out-File -FilePath $ReportPath -Encoding UTF8
Write-Ok "Report written to: $ReportPath"

Write-Info ""
Write-Ok "========================================"
Write-Ok "BepiPred3 Demo Complete"
Write-Ok "========================================"
Write-Info "Project ID : $projectId"
Write-Info "Job ID     : $jobId"
Write-Info "Scan ID    : $scanId"
Write-Info "Status     : $finalStatus"
Write-Info "Candidates : $candidateCount"
Write-Info "Duration   : $($duration.ToString('hh\:mm\:ss'))"
Write-Info "Report     : $ReportPath"
Write-Info "Frontend   : $FrontendUrl/epitope-screening?scan_id=$scanId"
Write-Ok "========================================"
