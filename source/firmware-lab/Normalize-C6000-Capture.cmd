@echo off
setlocal
set "ROOT=%~dp0.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
if "%~1"=="" (
  echo Usage: Normalize-C6000-Capture.cmd capture.jsonl [output.dibits] [--lsb-first] [--dibit-lsb-first] [--xor 2]
  exit /b 2
)
set "OUT=%~2"
if "%OUT%"=="" set "OUT=%~dpn1.dibits"
"%PYTHON%" "%~dp0normalize_c6000.py" --input "%~1" --output "%OUT%" %~3 %~4 %~5 %~6 %~7 %~8 %~9
endlocal
