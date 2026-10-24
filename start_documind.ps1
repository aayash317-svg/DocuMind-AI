Set-Location $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       Starting DocuMind AI Full Stack Services         " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Start Ollama
Write-Host "[1/3] Ensuring Ollama service is running..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ollama serve"

Start-Sleep -Seconds 2

# 2. Start FastAPI Backend
Write-Host "[2/3] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\.venv\Scripts\Activate.ps1; python -m uvicorn backend.app.main:app --port 8000"

Start-Sleep -Seconds 3

# 3. Start Vite Frontend
Write-Host "[3/3] Starting Vite Frontend on http://localhost:5173..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location frontend; npm run dev"

Write-Host "========================================================" -ForegroundColor Green
Write-Host "DocuMind AI is now running!" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173/" -ForegroundColor Green
Write-Host "Backend:  http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green

