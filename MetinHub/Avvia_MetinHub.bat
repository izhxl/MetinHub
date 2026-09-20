@echo off
setlocal DisableDelayedExpansion
set "METINHUB_AVVIO_DIR=%~dp0"
if exist "%METINHUB_AVVIO_DIR%MetinHub.exe" (
    start "" "%METINHUB_AVVIO_DIR%MetinHub.exe"
    exit /b
)
if not exist "%METINHUB_AVVIO_DIR%.venv\Scripts\python.exe" (
    echo Esegui prima Installa_MetinHub.bat.
    pause
    exit /b 1
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "try { $p=Join-Path $env:METINHUB_AVVIO_DIR '.venv\Scripts\python.exe'; Start-Process -FilePath $p -ArgumentList 'osserva_metin.py' -WorkingDirectory $env:METINHUB_AVVIO_DIR -Verb RunAs -ErrorAction Stop } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 pause
