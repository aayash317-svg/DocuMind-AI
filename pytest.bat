@echo off
if exist "%~dp0.venv\Scripts\pytest.exe" (
    "%~dp0.venv\Scripts\pytest.exe" %*
) else (
    pytest %*
)

