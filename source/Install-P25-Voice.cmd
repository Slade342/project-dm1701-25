@echo off
setlocal
cd /d "%~dp0"
title DM-1701 Experimental P25 Voice Firmware
if not exist ".venv\Scripts\python.exe" (
  echo Install DM-1701 Studio first.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -u firmware-voice\install.py
set "RESULT=%ERRORLEVEL%"
echo.
echo Installer exit code: %RESULT%
pause
exit /b %RESULT%
