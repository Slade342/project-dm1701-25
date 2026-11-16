#!/usr/bin/env python3
"""Build the standalone Project DM1701-25 macOS .app ZIP.

This is a native macOS application bundle launcher rather than a cross-compiled
Mach-O binary. It keeps the Python runtime in Application Support and works on
Intel and Apple-silicon Macs with a Python.org/Homebrew Python installation.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT.parent / "release" / "Project-DM1701-25-macOS.zip"


def copy_tree(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.name in {"__pycache__", ".pytest_cache", ".venv", "build", "codecs"}:
            continue
        destination = target / item.name
        if item.is_dir():
            copy_tree(item, destination)
        elif item.is_file():
            shutil.copy2(item, destination)


def build(output: Path) -> dict:
    stage = output.parent / ".project-dm1701-25-macos-stage"
    if stage.exists():
        shutil.rmtree(stage)
    app = stage / "Project-DM1701-25.app"
    contents = app / "Contents"
    resources = contents / "Resources"
    macos = contents / "MacOS"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    shutil.copy2(ROOT / "packaging-macos/Info.plist", contents / "Info.plist")
    launcher = macos / "Project-DM1701-25"
    shutil.copy2(ROOT / "packaging-macos/PROJECT-DM1701-25", launcher)
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    shutil.copy2(ROOT / "packaging-macos/README.txt", stage / "README.txt")

    app_source = resources / "app"
    for name in ("dm1701", "project_dm1701_25", "firmware-voice", "firmware-lab", "requirements.txt"):
        source = ROOT / name
        destination = app_source / name
        if source.is_dir():
            copy_tree(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    # The macOS app only needs the native firmware installer support files,
    # not the old capture-lab image or command runners.
    for path in (app_source / "firmware-lab").glob("*"):
        if path.name not in {"install.py", "vendor"}:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    for path in (app_source / "firmware-voice").glob("*"):
        if path.name.startswith(("DM1701-P25-VOICE-EXPERIMENTAL", "OPEN25-DM1701-P25-EXPERIMENTAL")) or path.suffix.lower() in {".elf", ".map", ".gz"}:
            path.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(stage).as_posix())
    shutil.rmtree(stage)
    return {"file": str(output), "bytes": output.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    print(build(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

