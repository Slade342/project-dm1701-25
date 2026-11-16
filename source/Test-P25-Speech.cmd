@echo off
setlocal
cd /d "%~dp0"
echo P25 SPEECH TEST - PC SPEAKER ONLY. No radio connection is required.
if exist .venv\Scripts\python.exe goto venv
py -3 firmware-p25\voice\speech_test.py --known --play
goto done
:venv
.venv\Scripts\python.exe firmware-p25\voice\speech_test.py --known --play
:done
echo.
echo The output WAV and report are in firmware-p25\voice\results.
pause
