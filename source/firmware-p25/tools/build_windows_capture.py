#!/usr/bin/env python3
"""Cross-compile the host P25 capture decoder for Windows x64 with Zig."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
zig = os.environ.get("DM1701_ZIG", "zig")
out = ROOT / "windows"
out.mkdir(exist_ok=True)
os.environ.setdefault("ZIG_GLOBAL_CACHE_DIR", str(ROOT / "build" / "zig-cache"))
os.environ.setdefault("ZIG_LOCAL_CACHE_DIR", str(ROOT / "build" / "zig-local"))
subprocess.run([
    zig, "cc", "-target", "x86_64-windows-gnu", "-O2", "-std=c11",
    "-I" + str(ROOT / "vendor" / "open25"),
    str(ROOT / "src" / "p25_capture.c"),
    str(ROOT / "vendor" / "open25" / "p25.c"),
    "-o", str(out / "p25-capture.exe"),
], cwd=ROOT, check=True)
print(out / "p25-capture.exe")
