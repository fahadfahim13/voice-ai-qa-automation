<#
.SYNOPSIS
    Launch the BizFinder Voice QA operator dashboard with a clean slate.

.DESCRIPTION
    `streamlit run` spawns a parent launcher AND an app child process. Killing
    only the port listener leaves a stale process that keeps serving OLD code
    (the cause of "Run suite not working" / stale AttributeError after edits).

    This script stops every Streamlit python process, frees the port, then
    launches a single fresh instance — so you always run the current code.

.PARAMETER Port
    Port to serve on. Default 8501.

.EXAMPLE
    pwsh scripts/run_dashboard.ps1
    pwsh scripts/run_dashboard.ps1 -Port 8502
#>
param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Stopping any existing Streamlit processes..." -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'streamlit' } |
    ForEach-Object {
        try {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
            Write-Host "  killed PID $($_.ProcessId)"
        } catch {}
    }

# Free the port if anything is still bound to it.
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {} }

Start-Sleep -Seconds 1

Write-Host "Launching dashboard on http://localhost:$Port ..." -ForegroundColor Green
Set-Location $repoRoot
uv run --extra report streamlit run backend/report/dashboard.py --server.port $Port
