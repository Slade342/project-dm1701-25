@echo off
setlocal
cd /d "%~dp0"
title DM-1701 Studio Setup
echo DM-1701 Studio - Windows Setup
echo Folder: %CD%
echo.
if not exist requirements.txt goto notextracted
if not exist setup_windows.py goto notextracted
echo [1/4] Looking for Python. Please leave this window open.
where py >nul 2>nul
if not errorlevel 1 goto launcher
where python >nul 2>nul
if not errorlevel 1 goto python
 echo Python was not found. Re-run the Python installer and enable the launcher.
goto failed
:launcher
py -3 -u setup_windows.py
if errorlevel 1 goto failed
goto done
:python
python -u setup_windows.py
if errorlevel 1 goto failed
goto done
:notextracted
echo Extract the complete ZIP first, then run this file from the extracted folder.
goto failed
:done
echo.
echo Setup finished. Starting DM-1701 Studio now.
call "%~dp0Start-Windows.cmd"
exit /b 0
:failed
echo.
echo Setup stopped. Send setup-windows.log and the text above for help.
echo If no log exists, Python did not start successfully.
pause
exit /b 1
