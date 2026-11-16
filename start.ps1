# Run from the extracted project folder; no PowerShell activation policy changes required.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host 'Open http://127.0.0.1:8000' -ForegroundColor Green
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
