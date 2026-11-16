@echo off
setlocal
cd /d "%~dp0"
title Project DM1701-25
if not exist .venv\Scripts\pythonw.exe (
  echo Project DM1701-25 is not installed. Run the single Project-DM1701-25-Setup.exe installer.
  pause
  exit /b 1
)
start "Project DM1701-25" ".venv\Scripts\pythonw.exe" -m project_dm1701_25

