# DocuMind AI Test Runner
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       Running DocuMind AI Backend Regression Tests" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

if (Test-Path "$ScriptDir\.venv\Scripts\python.exe") {
    Write-Host "[Using project virtual environment: .venv]" -ForegroundColor Green
    & "$ScriptDir\.venv\Scripts\python.exe" -m pytest $args
} else {
    Write-Host "[Using system python]" -ForegroundColor Yellow
    python -m pytest $args
}
