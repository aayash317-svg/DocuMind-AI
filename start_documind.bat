@echo off
cd /d "%~dp0"
echo ========================================================
echo       Starting DocuMind AI Full Stack Services
echo ========================================================
echo.

echo [1/3] Ensuring Ollama service is running...
start "Ollama Service" cmd /c "ollama serve"

timeout /t 2 /nobreak >nul

echo [2/3] Starting FastAPI Backend on http://127.0.0.1:8000...
start "DocuMind Backend" cmd /c "call .venv\Scripts\activate.bat && python -m uvicorn backend.app.main:app --port 8000"

timeout /t 3 /nobreak >nul

echo [3/3] Starting Vite Frontend on http://localhost:5173...
cd frontend
start "DocuMind Frontend" cmd /c "npm run dev"
cd ..

echo.
echo ========================================================
echo DocuMind AI is now running!
echo Frontend: http://localhost:5173/
echo Backend:  http://127.0.0.1:8000/docs
echo ========================================================

