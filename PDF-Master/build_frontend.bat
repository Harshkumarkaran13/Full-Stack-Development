@echo off
setlocal
cd /d "%~dp0frontend"
if not exist package.json (
  echo frontend/package.json not found.
  exit /b 1
)
echo Installing React frontend dependencies...
call npm install --no-audit --no-fund
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
cd /d "%~dp0"
echo.
echo React build generated in static\react.
