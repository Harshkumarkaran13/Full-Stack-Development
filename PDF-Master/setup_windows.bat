@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul || (echo Python Launcher was not found. Install Python 3.12 or newer with Tcl/Tk.& pause & exit /b 1)
where npm >nul 2>nul || (echo Node.js and npm were not found. Install Node.js 22.12 or newer first.& pause & exit /b 1)
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto failed
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto failed
pip install -r requirements.txt
if errorlevel 1 goto failed
pushd frontend
call npm install --no-audit --no-fund
if errorlevel 1 goto failed_frontend
call npm run build
if errorlevel 1 goto failed_frontend
popd
python manage.py migrate
if errorlevel 1 goto failed
python manage.py check
if errorlevel 1 goto failed
echo.
echo Setup complete. Run run_windows.bat to start PDF Master.
pause
exit /b 0
:failed_frontend
popd
goto failed
:failed
echo.
echo Setup failed. Review the error above and verify Python, Node.js and internet access.
pause
exit /b 1
