@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)
if not exist static\react\app.js (
  echo React frontend build not found. Run setup_windows.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python manage.py runserver
