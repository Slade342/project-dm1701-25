#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 DM-1701 Studio contributors
"""Render the actual radio C home layout and verify text bounds on the host."""
from pathlib import Path
import argparse
import subprocess

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--radiofoundry", type=Path, required=True)
args = parser.parse_args()
source = args.radiofoundry.resolve()
out = ROOT.parent / "build" / "radio-ui"
out.mkdir(parents=True, exist_ok=True)
command = ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wshadow", "-g",
           "-DGFX_INDEXED=1", "-DGFX_FB_BYTES=9600u", "-DGFX_MAX_ROWS=120u",
           "-DGFX_FIT_TRACE", "-DCONFIG_LANG_ES=0", "-DCONFIG_LANG_IT=0", "-DCONFIG_LANG_ZH=0",
           "-I" + str(ROOT), "-I" + str(ROOT / "test"),
           "-I" + str(source / "core"), "-I" + str(source / "hal"),
           str(ROOT / "test/render_home.c"), str(ROOT / "studio_home.c"),
           *(str(source / "core/ui" / name) for name in ("gfx.c", "fonts.c", "fmt.c")),
           "-o", str(out / "test-render")]
subprocess.run(command, check=True)
subprocess.run([str(out / "test-render"), str(out / "radio-home.ppm")], check=True)
subprocess.run(["convert", str(out / "radio-home.ppm"), str(ROOT / "radio-home-preview.png")], check=True)
print(ROOT / "radio-home-preview.png")
