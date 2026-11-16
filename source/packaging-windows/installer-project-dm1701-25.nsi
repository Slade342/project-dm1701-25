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
Name "Project DM1701-25 0.4"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Project DM1701-25"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "Project DM1701-25 — experimental P25 / DMR / FM CPS"
VIProductVersion "0.4.0.0"
VIAddVersionKey "ProductName" "Project DM1701-25"
VIAddVersionKey "FileDescription" "Project DM1701-25 Windows Setup"
VIAddVersionKey "FileVersion" "0.4.0"
VIAddVersionKey "LegalCopyright" "Project DM1701-25 contributors; bundled components retain their licenses"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Install Project DM1701-25"
!define MUI_WELCOMEPAGE_TEXT "This installs the standalone Project DM1701-25 CPS for the Baofeng DM-1701 / Retevis RT84.$\r$\n$\r$\nThe desktop shortcut opens the application directly. The optional experimental P25 firmware installer is inside the Firmware page.$\r$\n$\r$\nThe small setup downloads official Python 3.12 only when a suitable 64-bit runtime is not already present."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchProjectDM170125
!define MUI_FINISHPAGE_RUN_TEXT "Open Project DM1701-25"
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

Section "Project DM1701-25" MainSection
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${STAGE}/*"
  DetailPrint "Preparing the Project DM1701-25 application runtime and bundled packages..."
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\installer\install_runtime.ps1" -AppDir "$INSTDIR"'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_ICONSTOP "Setup could not prepare Project DM1701-25.$\r$\nRead $INSTDIR\setup-windows.log for the exact error."
    SetErrorLevel 1
    Abort
  ${EndIf}
  SetOutPath "$INSTDIR"
  CreateShortCut "$DESKTOP\Project-DM1701-25.lnk" "$INSTDIR\.venv\Scripts\pythonw.exe" "-m project_dm1701_25" "$INSTDIR\.venv\Scripts\pythonw.exe" 0 SW_SHOWNORMAL
  CreateDirectory "$SMPROGRAMS\Project DM1701-25"
  CreateShortCut "$SMPROGRAMS\Project DM1701-25\Project-DM1701-25.lnk" "$INSTDIR\.venv\Scripts\pythonw.exe" "-m project_dm1701_25" "$INSTDIR\.venv\Scripts\pythonw.exe" 0 SW_SHOWNORMAL
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortCut "$SMPROGRAMS\Project DM1701-25\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectDM170125" "DisplayName" "Project DM1701-25 0.4"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectDM170125" "DisplayVersion" "0.4.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectDM170125" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectDM170125" "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectDM170125" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectDM170125" "NoRepair" 1
SectionEnd

Function LaunchProjectDM170125
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\.venv\Scripts\pythonw.exe" -m project_dm1701_25'
FunctionEnd

Section "Uninstall"
  SetShellVarContext current
  MessageBox MB_YESNO|MB_ICONQUESTION "Remove Project DM1701-25? Your codeplug files in Documents are kept." IDYES +2
  Abort
  Delete "$DESKTOP\Project-DM1701-25.lnk"
  Delete "$SMPROGRAMS\Project DM1701-25\Project-DM1701-25.lnk"
  Delete "$SMPROGRAMS\Project DM1701-25\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Project DM1701-25"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectDM170125"
  !include "${DELETE_LIST}"
  RMDir /r "$INSTDIR\.venv"
  RMDir /r "$INSTDIR\installer"
  Delete "$INSTDIR\setup-windows.log"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd

