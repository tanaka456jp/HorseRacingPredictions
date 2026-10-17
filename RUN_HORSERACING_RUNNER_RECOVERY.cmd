@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\recover_self_hosted_runner.ps1"
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" (
  echo Runner recovery FAILED with exit code %EXITCODE%.
) else (
  echo Runner recovery completed. The existing GitHub runner listener is running.
)
pause
exit /b %EXITCODE%
