# SPDX-License-Identifier: MIT
# DM-1701 Studio Windows setup: local runtime and bundled dependencies.
param([Parameter(Mandatory=$true)][string]$AppDir)
$ErrorActionPreference = 'Stop'
$AppDir = [System.IO.Path]::GetFullPath($AppDir)
$LogPath = Join-Path $AppDir 'setup-windows.log'
Start-Transcript -Path $LogPath -Force | Out-Null
try {
    Write-Host 'Preparing DM-1701 Studio 0.3...'
    $PythonExe = $null
    $Candidates = @()
    $PrivatePython = Join-Path $AppDir 'Python\python.exe'
    if (Test-Path -LiteralPath $PrivatePython) {
        $Candidates += @{Exe=$PrivatePython; Prefix=@()}
    }
    foreach ($Name in @('py.exe', 'python.exe', 'python3.exe')) {
        $Command = Get-Command $Name -ErrorAction SilentlyContinue
        if ($Command -and $Command.Source -notlike '*\WindowsApps\*') {
            $Prefix = @()
            if ($Name -eq 'py.exe') { $Prefix = @('-3') }
            $Candidates += @{Exe=$Command.Source; Prefix=$Prefix}
        }
    }
    foreach ($Candidate in $Candidates) {
        $ProbeArguments = @($Candidate.Prefix) + @('-c', 'import sys, struct, tkinter; assert sys.version_info[:2] == (3,12) and struct.calcsize("P") == 8; print(sys.executable)')
        try {
            $Answer = & $Candidate.Exe @ProbeArguments 2>$null
            if ($LASTEXITCODE -eq 0 -and $Answer) {
                $Found = @($Answer)[-1].Trim()
                if (Test-Path -LiteralPath $Found) {
                    $PythonExe = $Found
                    break
                }
            }
        } catch { }
    }
    if (-not $PythonExe) {
        Write-Host 'Setting up Python 3.12 with Tk...'
        $PythonSetup = Join-Path $AppDir 'installer\python-3.12.10-amd64.exe'
        $ExpectedHash = '67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb'
        if (-not (Test-Path -LiteralPath $PythonSetup)) {
            Write-Host 'Downloading the official Python runtime automatically...'
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $PythonDownload = $PythonSetup + '.download'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $PythonDownload
            if ((Get-FileHash -LiteralPath $PythonDownload -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedHash) {
                throw 'The downloaded Python installer failed its SHA-256 check.'
            }
            Move-Item -LiteralPath $PythonDownload -Destination $PythonSetup -Force
        }
        if ((Get-FileHash -LiteralPath $PythonSetup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedHash) {
            throw 'The Python installer failed its SHA-256 check.'
        }
        $Signature = Get-AuthenticodeSignature -LiteralPath $PythonSetup
        if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
            throw ('The Python installer did not pass Windows signature verification: ' + $Signature.Status)
        }
        $Arguments = @('/quiet', 'InstallAllUsers=0', 'Include_launcher=0', 'Include_tcltk=1',
            'Include_pip=1', 'Include_test=0', 'Include_doc=0', 'AssociateFiles=0',
            'Shortcuts=0', 'PrependPath=0', ('TargetDir="' + (Join-Path $AppDir 'Python') + '"'))
        $Process = Start-Process -FilePath $PythonSetup -ArgumentList $Arguments -PassThru -Wait
        if ($Process.ExitCode -notin @(0,3010)) { throw ('Python setup stopped with code ' + $Process.ExitCode) }
        $PythonExe = $PrivatePython
        if (-not (Test-Path -LiteralPath $PythonExe)) {
            throw 'Python setup did not create its expected interpreter. Install Python 3.10+ with Tk, then run Studio setup again.'
        }
    }
    Write-Host ('Using Python: ' + $PythonExe)
    $Venv = Join-Path $AppDir '.venv'
    & $PythonExe -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the application Python environment.' }
    $StudioPython = Join-Path $Venv 'Scripts\python.exe'
    Write-Host 'Installing included application packages (no package downloads)...'
    & $StudioPython -m pip --disable-pip-version-check install --no-index --find-links (Join-Path $AppDir 'installer\wheels') -r (Join-Path $AppDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'The bundled application packages could not be installed.' }
    & $StudioPython -c 'import tkinter, yaml, customtkinter, serial, usb.core; print("Studio dependencies are ready.")'
    if ($LASTEXITCODE -ne 0) { throw 'Application dependency verification failed.' }
    Write-Host 'Installation completed. Use the DM-1701 Studio desktop shortcut.'
    Stop-Transcript | Out-Null
    exit 0
} catch {
    Write-Host ('Setup stopped: ' + $_.Exception.Message)
    Write-Host ('Setup log: ' + $LogPath)
    Stop-Transcript | Out-Null
    exit 1
}
