@echo off
setlocal EnableExtensions EnableDelayedExpansion
if "%~1"=="" (
  echo Usage: Try-C6000-Mappings.cmd capture.jsonl
  echo Runs all eight documented byte/dibit/polarity candidates and writes reports beside the capture.
  exit /b 2
)
set "ROOT=%~dp0.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
if not exist "%ROOT%\firmware-p25\windows\p25-capture.exe" (
  echo Windows P25 decoder is missing from this package.
  exit /b 2
)
set "BASE=%~dpn1"
set "FAIL=0"
for %%L in (0 1) do for %%D in (0 1) do for %%X in (0 2) do (
  set "TAG=L%%L-D%%D-X%%X"
  set "ARGS="
  if %%L==1 set "ARGS=!ARGS! --lsb-first"
  if %%D==1 set "ARGS=!ARGS! --dibit-lsb-first"
  if %%X==2 set "ARGS=!ARGS! --xor 2"
  set "DIB=!BASE!-!TAG!.dibits"
  set "JSON=!BASE!-!TAG!.p25.jsonl"
  echo.
  echo === !TAG! !ARGS! ===
  "%PYTHON%" "%~dp0normalize_c6000.py" --input "%~1" --output "!DIB!" !ARGS!
  if errorlevel 1 (
    echo Normalization failed for !TAG!.
    set "FAIL=1"
  ) else (
    "%ROOT%\firmware-p25\windows\p25-capture.exe" --dibits --nac any "!DIB!" > "!JSON!"
    set "CODE=!ERRORLEVEL!"
    echo Decoder exit !CODE! ^(0=clean frame, 1=no clean frame, 2=input/tool error^)
    echo Report: !JSON!
    if !CODE! GTR 1 set "FAIL=1"
  )
)
echo.
echo Finished. A candidate is only interesting if it produces valid frames that agree
echo with the SDR recording; a host frame does not qualify the radio speaker path.
endlocal & exit /b %FAIL%
