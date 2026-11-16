#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the reduced ARM P25 protocol + IMBE component; never flashes hardware."""
from pathlib import Path
import argparse
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--zig", required=True)
args = parser.parse_args()
env = os.environ.copy()
env.setdefault("ZIG_GLOBAL_CACHE_DIR", str(ROOT / "build" / "zig-cache"))
env.setdefault("ZIG_LOCAL_CACHE_DIR", str(ROOT / "build" / "zig-local"))
subprocess.run(["python3", str(ROOT / "tools" / "arm_check.py"), "--zig", args.zig], cwd=ROOT, env=env, check=True)
env["DM1701_ZIG"] = args.zig
subprocess.run(["python3", str(ROOT / "voice" / "build_arm_codec.py")], cwd=ROOT / "voice", env=env, check=True)
output = ROOT / "build" / "arm" / "p25-audio-imbe.o"
objects = [ROOT / "build" / "arm" / "p25.o", ROOT / "build" / "arm" / "p25-audio-pipeline.o",
           ROOT / "build" / "arm" / "c6000-symbol-adapter.o", ROOT / "build" / "arm" / "p25-speaker-fifo.o"]
objects += sorted((ROOT / "voice" / "build-arm").glob("*.o"))
subprocess.run([args.zig, "c++", "-target", "thumb-freestanding-eabi", "-mcpu=cortex_m4", "-mthumb",
                "-nostdlib", "-r", *map(str, objects), "-o", str(output)], cwd=ROOT, env=env, check=True)
undefined = subprocess.run(["nm", "-u", str(output)], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
if undefined:
    raise SystemExit("unresolved ARM symbols remain:\n" + undefined)
size = subprocess.run(["size", str(output)], cwd=ROOT, text=True, capture_output=True, check=True).stdout.splitlines()[-1].split()
report = {"object": str(output.relative_to(ROOT)), "text_bytes": int(size[0]), "data_bytes": int(size[1]),
          "bss_bytes": int(size[2]), "total_bytes": int(size[3]), "target": "Cortex-M4 / Thumb",
          "flashable": False, "radio_qualified": False, "rf_tx": False,
          "components": ["P25 NID/FEC/frame recovery", "C6000 raw36-to-dibit adapter (mapping configurable)",
                         "IMBE fixed-point decoder", "bounded speaker PCM FIFO/callback pipeline"]}
(ROOT / "build" / "arm" / "p25-audio-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
