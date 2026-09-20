@echo off
setlocal DisableDelayedExpansion
set "METINHUB_SETUP_DIR=%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -STA -ExecutionPolicy Bypass -File "%METINHUB_SETUP_DIR%Installa_MetinHub.ps1"
if errorlevel 1 pause
