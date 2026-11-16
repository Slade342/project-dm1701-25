@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title DM-1701 Studio Installer
set "APPDIR=%LOCALAPPDATA%\DM1701 Studio"
echo Installing DM-1701 Studio to:
echo %APPDIR%
echo.
if not exist "%APPDIR%" mkdir "%APPDIR%"
robocopy "%~dp0" "%APPDIR%" /E /XD .venv build __pycache__ /XF "*.log" >nul
if errorlevel 8 (
  echo Copy failed. Check that the package is fully extracted and try again.
  pause
  exit /b 1
)
call "%APPDIR%\Setup-Windows.cmd"
if errorlevel 1 exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\DM-1701 Studio.lnk'); $s.TargetPath='%APPDIR%\Start-Windows.cmd'; $s.WorkingDirectory='%APPDIR%'; $s.IconLocation='%APPDIR%\DM1701-Studio.ico'; $s.Save()"
echo.
echo DM-1701 Studio is installed. A desktop shortcut was created.
echo You can close this window.
pause
