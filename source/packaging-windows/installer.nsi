; SPDX-License-Identifier: MIT
Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!ifndef STAGE
!error "Pass -DSTAGE=/absolute/staged/payload"
!endif
!ifndef OUTPUT
!error "Pass -DOUTPUT=/absolute/output.exe"
!endif
Name "DM-1701 Studio 0.3"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\DM1701 Studio"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "DM-1701 Studio — Experimental 0.3"
VIProductVersion "0.3.0.0"
VIAddVersionKey "ProductName" "DM-1701 Studio"
VIAddVersionKey "FileDescription" "DM-1701 Studio Windows Setup"
VIAddVersionKey "FileVersion" "0.3.0"
VIAddVersionKey "LegalCopyright" "DM-1701 Studio contributors; bundled components retain their licenses"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Install DM-1701 Studio"
!define MUI_WELCOMEPAGE_TEXT "This setup installs the desktop application and all Python packages, then creates a desktop shortcut.$\r$\n$\r$\nIt uses 64-bit Python 3.12 when available and sets up Python automatically if needed. The small web installer downloads Python from python.org when required.$\r$\n$\r$\nRadio firmware installation is a separate action in the application."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchStudio
!define MUI_FINISHPAGE_RUN_TEXT "Open DM-1701 Studio"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "This package requires 64-bit Windows 10 or later."
    Abort
  ${EndIf}
FunctionEnd

Section "DM-1701 Studio" MainSection
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${STAGE}/*"
  DetailPrint "Preparing the application runtime and bundled packages..."
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\installer\install_runtime.ps1" -AppDir "$INSTDIR"'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_ICONSTOP "Setup could not prepare the application runtime.$\r$\nRead $INSTDIR\setup-windows.log for the exact error.$\r$\nThe files are retained so setup can be rerun."
    SetErrorLevel 1
    Abort
  ${EndIf}
  SetOutPath "$INSTDIR"
  CreateShortCut "$DESKTOP\DM-1701 Studio.lnk" "$INSTDIR\.venv\Scripts\pythonw.exe" "-m dm1701" "$INSTDIR\.venv\Scripts\pythonw.exe" 0 SW_SHOWNORMAL
  CreateDirectory "$SMPROGRAMS\DM-1701 Studio"
  CreateShortCut "$SMPROGRAMS\DM-1701 Studio\DM-1701 Studio.lnk" "$INSTDIR\.venv\Scripts\pythonw.exe" "-m dm1701" "$INSTDIR\.venv\Scripts\pythonw.exe" 0 SW_SHOWNORMAL
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortCut "$SMPROGRAMS\DM-1701 Studio\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DM1701Studio" "DisplayName" "DM-1701 Studio 0.3"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DM1701Studio" "DisplayVersion" "0.3.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DM1701Studio" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DM1701Studio" "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DM1701Studio" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DM1701Studio" "NoRepair" 1
SectionEnd

Function LaunchStudio
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\.venv\Scripts\pythonw.exe" -m dm1701'
FunctionEnd

Section "Uninstall"
  SetShellVarContext current
  MessageBox MB_YESNO|MB_ICONQUESTION "Remove DM-1701 Studio? Your codeplug files in Documents are kept." IDYES +2
  Abort
  Delete "$DESKTOP\DM-1701 Studio.lnk"
  Delete "$SMPROGRAMS\DM-1701 Studio\DM-1701 Studio.lnk"
  Delete "$SMPROGRAMS\DM-1701 Studio\Uninstall.lnk"
  RMDir "$SMPROGRAMS\DM-1701 Studio"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DM1701Studio"
  ; The installer uses this fixed per-user directory and offers no directory picker.
  ; Keep a privately installed Python registered with Windows so its own uninstaller
  ; can manage it. Remove Studio files individually from the generated file list.
  !include "${DELETE_LIST}"
  RMDir /r "$INSTDIR\.venv"
  RMDir /r "$INSTDIR\installer"
  Delete "$INSTDIR\setup-windows.log"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
