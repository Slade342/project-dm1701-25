@echo off
setlocal
cd /d "%~dp0"
title DM-1701 Studio
if not exist .venv\Scripts\pythonw.exe (
  echo First run: installing DM-1701 Studio dependencies.
  call Setup-Windows.cmd
  if errorlevel 1 exit /b 1
)
start "DM-1701 Studio" ".venv\Scripts\pythonw.exe" -m dm1701
