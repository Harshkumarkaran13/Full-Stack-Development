$ErrorActionPreference = 'Stop'
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Exe = Join-Path $AppDir 'dist\PDFMasterLocker.exe'
$Script = Join-Path $AppDir 'locker.pyw'
$ProjectRoot = Split-Path -Parent $AppDir
$VenvPythonw = Join-Path $ProjectRoot '.venv\Scripts\pythonw.exe'

if (Test-Path $Exe) {
    $Launcher = $Exe
    $Arguments = '"%1"'
} elseif (Test-Path $VenvPythonw) {
    $Launcher = $VenvPythonw
    $Arguments = '"' + $Script + '" "%1"'
} else {
    $PyLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if (-not $PyLauncher) {
        throw 'Python Launcher (py.exe) was not found. Install Python 3 for Windows first.'
    }
    $Pythonw = (& $PyLauncher.Source -3 -c "import sys,pathlib; p=pathlib.Path(sys.executable).with_name('pythonw.exe'); print(p if p.exists() else sys.executable)").Trim()
    if (-not (Test-Path $Pythonw)) {
        throw "Could not locate Python: $Pythonw"
    }
    $Launcher = $Pythonw
    $Arguments = '"' + $Script + '" "%1"'
}

$Command = '"' + $Launcher + '" ' + $Arguments
$ExtensionKey = 'HKCU:\Software\Classes\.pmlock'
$ProgIdKey = 'HKCU:\Software\Classes\PDFMaster.LockedItem'
$OpenCommandKey = Join-Path $ProgIdKey 'shell\open\command'
New-Item -Path $ExtensionKey -Force | Out-Null
Set-Item -Path $ExtensionKey -Value 'PDFMaster.LockedItem'
New-Item -Path $ProgIdKey -Force | Out-Null
Set-Item -Path $ProgIdKey -Value 'PDF Master Protected Item'
New-Item -Path $OpenCommandKey -Force | Out-Null
Set-Item -Path $OpenCommandKey -Value $Command

Write-Host 'Registered .pmlock files for the current Windows user.' -ForegroundColor Green
Write-Host 'Double-click a .pmlock item to open PDF Master Locker.'
Write-Host 'If Windows asks which app to use, choose PDF Master Locker.'
