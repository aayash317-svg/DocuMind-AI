@echo off
cd /d "%~dp0"
echo ========================================================
echo       Running DocuMind AI Backend Regression Tests
echo ========================================================
if exist ".venv\Scripts\python.exe" (
    echo [Using project virtual environment: .venv]
    ".venv\Scripts\python.exe" -m pytest %*
) else (
    echo [Using system python/pytest]
    python -m pytest %*
)
