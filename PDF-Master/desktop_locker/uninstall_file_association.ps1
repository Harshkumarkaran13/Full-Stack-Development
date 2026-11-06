$ErrorActionPreference = 'Stop'
Remove-Item -Path 'HKCU:\Software\Classes\.pmlock' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path 'HKCU:\Software\Classes\PDFMaster.LockedItem' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'Removed the PDF Master .pmlock file association for the current user.' -ForegroundColor Green
