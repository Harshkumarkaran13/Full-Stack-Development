@echo off
setlocal
cd /d "%~dp0"
set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" locker.pyw
) else (
    py -3 locker.pyw
)
if errorlevel 1 pause
