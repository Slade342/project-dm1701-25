#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the single-file Windows setup using Linux NSIS and pinned payloads.

The resulting PE installer is compiled here; actual installation on Windows
still requires a Windows run. Assets are downloaded over HTTPS, hash checked,
and the official Python signature is also checked by Windows before execution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
ASSETS = WORK / 'windows-setup-assets'
TOOLS = WORK / 'windows-setup-tools'
PYTHON_URL = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'
PYTHON_SHA = '67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb'
PYTHON_FILE = ASSETS / 'python-3.12.10-amd64.exe'
SKIP = {'build', 'build-arm', '__pycache__', '.cache', '.venv', '.git', '.pytest_cache', '.agents'}
SKIP_SUFFIX = {'.pyc', '.o', '.a', '.so', '.d', '.pdb'}

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def download(url: str, path: Path, expected: str | None = None) -> None:
    if path.is_file() and (expected is None or sha(path) == expected):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read()
    if expected and hashlib.sha256(payload).hexdigest() != expected:
        raise RuntimeError(f'{path.name} hash mismatch')
    path.write_bytes(payload)

def prepare_assets(*, bundle_python: bool = True) -> tuple[Path, dict[str, str]]:
    if bundle_python:
        download(PYTHON_URL, PYTHON_FILE, PYTHON_SHA)
    wheels = ASSETS / 'wheels'
    wheels.mkdir(parents=True, exist_ok=True)
    if not list(wheels.glob('*.whl')):
        subprocess.run([os.sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
            '--platform', 'win_amd64', '--python-version', '312', '--implementation', 'cp',
            '--abi', 'cp312', '-r', str(ROOT / 'requirements.txt'), '-d', str(wheels)], check=True)
    # NSIS 3.08 is the Debian 12 build and runs on older Linux build hosts too.
    binary = TOOLS / 'root/usr/bin/makensis'
    if not binary.is_file():
        base = 'https://deb.debian.org/debian/pool/main/n/nsis/'
        for filename in ('nsis_3.08-3+deb12u1_amd64.deb', 'nsis-common_3.08-3+deb12u1_all.deb'):
            package = TOOLS / filename
            download(base + filename, package)
            subprocess.run(['dpkg-deb', '-x', str(package), str(TOOLS / 'root')], check=True)
    return binary, {p.name: sha(p) for p in sorted(wheels.glob('*.whl'))}

def files(*, web_bootstrap: bool = False, open25: bool = False):
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP for part in rel.parts) or path.suffix.lower() in SKIP_SUFFIX:
            continue
        if open25:
            # The new product is a single application, not the old capture
            # lab folder. Keep only assets needed by the CPS/voice installer.
            rel_text = rel.as_posix()
            if rel.parts and rel.parts[0] in {"tests", "firmware-lab"}:
                if not (rel_text.startswith("firmware-lab/vendor/") or rel_text == "firmware-lab/install.py"):
                    continue
            if rel_text.startswith("firmware-p25/"):
                continue
            if path.name.startswith(("DM1701-", "Setup", "Start", "Install-Capture", "Test-P25")):
                continue
            if path.name == "Install-P25-Voice.cmd" or "DM-1701 Studio.app" in rel_text:
                continue
            if path.name in {"README.md", "FIRMWARE.md", "MACOS.md", "P25-RESEARCH.md", "VALIDATION.md",
                             "WINDOWS.md", "START-HERE.md", "SPEECH-TEST-UPDATE.txt", "run.command"}:
                continue
            if rel_text.startswith("firmware-voice/") and (
                path.name.startswith(("DM1701-P25-VOICE-EXPERIMENTAL", "OPEN25-DM1701-P25-EXPERIMENTAL")) or
                path.name.endswith(".tar.gz") or path.name.endswith(".tar.xz") or path.suffix.lower() in {".elf", ".map"}):
                continue
        if web_bootstrap and (path.suffix.lower() in {'.elf', '.map'}
                              or rel.as_posix() == 'firmware-voice/RadioFoundry-Studio-Source-0.3.tar.gz'):
            continue
        yield path, rel

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--web-bootstrap', action='store_true', help='Small setup: fetch Python only when needed and offer corresponding firmware source separately')
    parser.add_argument('--open25', action='store_true', help='Compatibility alias for the Project DM1701-25 product')
    parser.add_argument('--project25', action='store_true', help='Build the standalone Project DM1701-25 product')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output is None:
        if args.open25 or args.project25:
            args.output = WORK / ('release/Project-DM1701-25-Setup-0.4-Web.exe' if args.web_bootstrap else 'release/Project-DM1701-25-Setup-0.4.exe')
        else:
            args.output = WORK / ('release/DM1701-Studio-Setup-0.3-Web.exe' if args.web_bootstrap else 'release/DM1701-Studio-Setup-0.3.exe')
    compiler, wheels = prepare_assets(bundle_python=not args.web_bootstrap)
    if args.prepare_only:
        print(json.dumps({'compiler': str(compiler), 'python_sha256': PYTHON_SHA, 'wheels': wheels}, indent=2))
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='studio-setup-', dir=WORK) as temp:
        stage = Path(temp) / 'payload'
        stage.mkdir()
        included = []
        for path, rel in files(web_bootstrap=args.web_bootstrap, open25=(args.open25 or args.project25)):
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            included.append(rel)
        installer = stage / 'installer'
        installer.mkdir()
        if not args.web_bootstrap:
            shutil.copy2(PYTHON_FILE, installer)
        shutil.copy2(ROOT / 'packaging-windows/install_runtime.ps1', installer)
        shutil.copytree(ASSETS / 'wheels', installer / 'wheels')
        record = {'python': {'url': PYTHON_URL, 'sha256': PYTHON_SHA, 'bundled': not args.web_bootstrap}, 'wheels': wheels,
                  'windows_execution_tested': False}
        (installer / 'assets.json').write_text(json.dumps(record, indent=2) + '\n')
        if args.web_bootstrap:
            (installer / 'SOURCE-OFFER.txt').write_text(
                'This installer includes GPL P25 receiver components. Complete corresponding\n'
                'Project DM1701-25 integration source is in Project-DM1701-25-Source-0.4.zip in this folder.\n'
                'The matching source archives are available from the Project DM1701-25 release page.\n'
                'No proprietary donor firmware is included.\n', encoding='utf-8')
        # The complete provided Studio source accompanies the GPL components.
        # RadioFoundry's pinned base source must be included separately by the
        # firmware builder as firmware-voice/source or a source archive.
        source_archive = installer / ('Project-DM1701-25-Source-0.4.zip' if (args.open25 or args.project25) else 'DM1701-Studio-Source-0.3.zip')
        with zipfile.ZipFile(source_archive, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path, rel in files(web_bootstrap=args.web_bootstrap, open25=(args.open25 or args.project25)):
                if path.suffix.lower() in {'.bin', '.elf', '.map', '.exe', '.png', '.wav', '.ppm', '.gz'}:
                    continue
                archive.write(path, ('Project-DM1701-25/' if (args.open25 or args.project25) else 'DM1701-Studio/') + rel.as_posix())
        shutil.copy2(source_archive, args.output.parent / ('Project-DM1701-25-Source-0.4.zip' if (args.open25 or args.project25) else 'DM1701-Studio-Source-0.3.zip'))
        deletes = Path(temp) / 'uninstall-files.nsh'
        lines = ['Delete "$INSTDIR\\' + str(rel).replace('/', '\\') + '"' for rel in included]
        directories = {parent for rel in included for parent in rel.parents if str(parent) != '.'}
        lines += ['RMDir "$INSTDIR\\' + str(rel).replace('/', '\\') + '"'
                  for rel in sorted(directories, key=lambda rel: len(rel.parts), reverse=True)]
        deletes.write_text('\n'.join(lines) + '\n')
        environment = dict(os.environ, NSISDIR=str(TOOLS / 'root/usr/share/nsis'))
        subprocess.run([str(compiler), '-V3', '-DSTAGE=' + str(stage),
            '-DOUTPUT=' + str(args.output.resolve()), '-DDELETE_LIST=' + str(deletes),
            str(ROOT / ('packaging-windows/installer-project-dm1701-25.nsi' if (args.open25 or args.project25) else 'packaging-windows/installer.nsi'))], check=True, env=environment)
    report = {'file': str(args.output), 'bytes': args.output.stat().st_size,
              'sha256': sha(args.output), 'windows_execution_tested': False,
              'bundled_python': None if args.web_bootstrap else '3.12.10 amd64',
              'python_download_if_missing': PYTHON_URL if args.web_bootstrap else None,
              'web_bootstrap': args.web_bootstrap, 'project_dm1701_25': (args.open25 or args.project25), 'offline_dependency_wheels': len(wheels)}
    if args.web_bootstrap and report['bytes'] >= 25 * 1024 * 1024:
        raise RuntimeError('Web bootstrap exceeds the 25 MiB static asset limit')
    args.output.with_suffix('.build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
