@echo off
setlocal
set "ROOT=%~dp0.."
if "%~1"=="" (
  echo Usage: Decode-C6000-Capture.cmd capture.jsonl [output-prefix] [--lsb-first] [--dibit-lsb-first] [--xor 2]
  exit /b 2
)
set "DIB=%~dpn1.dibits"
set "JSON=%~dpn1.p25.jsonl"
if not "%~2"=="" (
  set "DIB=%~2.dibits"
  set "JSON=%~2.p25.jsonl"
)
call "%~dp0Normalize-C6000-Capture.cmd" "%~1" "%DIB%" %~3 %~4 %~5 %~6 %~7 %~8 %~9
if errorlevel 1 exit /b %ERRORLEVEL%
if not exist "%ROOT%\firmware-p25\windows\p25-capture.exe" (
  echo Windows P25 decoder is missing from this package.
  exit /b 2
)
"%ROOT%\firmware-p25\windows\p25-capture.exe" --dibits --nac any "%DIB%" > "%JSON%"
set "CODE=%ERRORLEVEL%"
echo Decoder report: "%JSON%"
echo Exit code %CODE% means 0=at least one clean frame, 1=no clean frames, 2=input/tool error.
endlocal & exit /b %CODE%
