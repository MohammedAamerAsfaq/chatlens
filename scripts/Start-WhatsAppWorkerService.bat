@echo off
setlocal

fltmc >nul 2>&1
if errorlevel 1 (
    powershell.exe -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-WhatsAppWorkerService.ps1"
if errorlevel 1 (
    echo.
    echo Failed to start ChatLensWorker. Review the error above.
    pause
    exit /b 1
)
endlocal
