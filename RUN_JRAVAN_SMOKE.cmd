@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_jravan_trial.ps1"
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" (
  echo JRA-VAN smoke FAILED. Check artifacts\jravan_support_bundle.zip
) else (
  echo JRA-VAN smoke PASS.
)
pause
exit /b %EXITCODE%
