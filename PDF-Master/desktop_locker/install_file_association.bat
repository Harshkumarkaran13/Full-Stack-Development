@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_file_association.ps1"
if errorlevel 1 (
    echo File association setup failed. Review the message above.
    pause
    exit /b 1
)
pause
