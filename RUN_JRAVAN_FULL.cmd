@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_jravan_trial.ps1" -Full
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" (
  echo JRA-VAN full trial FAILED. Check artifacts\jravan_support_bundle.zip
) else (
  echo JRA-VAN full trial PASS.
  echo Current history: data\jravan\full\current_history.csv
)
pause
exit /b %EXITCODE%
