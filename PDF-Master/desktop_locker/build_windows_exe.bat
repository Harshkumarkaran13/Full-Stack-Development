@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller cryptography
if errorlevel 1 goto failed
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name PDFMasterLocker locker.pyw
if errorlevel 1 goto failed
echo.
echo Built: %~dp0dist\PDFMasterLocker.exe
echo Run install_file_association.bat again to associate .pmlock files with the EXE.
pause
exit /b 0
:failed
echo Build failed. Check the error shown above.
pause
exit /b 1
