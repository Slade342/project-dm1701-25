@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Run Setup-Windows.cmd first.
  pause
  exit /b 1
)
start "DM-1701 Studio" ".venv\Scripts\pythonw.exe" -m dm1701
