@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_jravan_trial.ps1" -Resume
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" (
  echo JRA-VAN resume FAILED. Check artifacts\jravan_support_bundle.zip
) else (
  echo JRA-VAN resume PASS.
  echo Current history: data\jravan\full\current_history.csv
)
pause
exit /b %EXITCODE%
