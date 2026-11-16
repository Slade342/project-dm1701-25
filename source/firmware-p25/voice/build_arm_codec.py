#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-compile the reduced fixed-point IMBE decoder archive for Cortex-M4."""
from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
ZIG = os.environ.get("DM1701_ZIG", "zig")
OUT = ROOT / "build-arm"
OUT.mkdir(exist_ok=True)
os.environ.setdefault("ZIG_GLOBAL_CACHE_DIR", str(ROOT.parent.parent / "build" / "zig-cache"))
os.environ.setdefault("ZIG_LOCAL_CACHE_DIR", str(ROOT.parent.parent / "build" / "zig-local"))
common = [ZIG, "c++", "-target", "thumb-freestanding-eabi", "-mcpu=cortex_m4", "-mthumb", "-Os",
          "-ffreestanding", "-fno-exceptions", "-fno-rtti", "-fno-unwind-tables",
          "-fno-asynchronous-unwind-tables", "-std=c++14", "-Wno-header-guard",
          "-I" + str(ROOT / "arm_compat"), "-I" + str(ROOT / "vendor")]
decode_sources = ["aux_sub.cc", "basicop2.cc", "ch_decode.cc", "ch_encode.cc", "decode.cc",
                  "dc_rmv.cc", "dsp_sub.cc", "encode.cc", "imbe_vocoder_impl.cc", "math_sub.cc",
                  "pe_lpf.cc", "pitch_est.cc", "pitch_ref.cc", "qnt_sub.cc", "rand_gen.cc",
                  "sa_decode.cc", "sa_encode.cc", "sa_enh.cc", "tbls.cc", "uv_synt.cc",
                  "v_synt.cc", "v_uv_det.cc"]
objects = []
for name in decode_sources:
    source = ROOT / "vendor" / name
    target = OUT / (source.stem + ".o")
    subprocess.run(common + ["-c", str(source), "-o", str(target)], check=True, cwd=ROOT)
    objects.append(target)
for source in (ROOT / "arm" / "p25_imbe_arm.cc", ROOT / "arm" / "arm_runtime.c"):
    compiler = common if source.suffix == ".cc" else [ZIG, "cc", "-target", "thumb-freestanding-eabi", "-mcpu=cortex_m4", "-mthumb", "-Os", "-ffreestanding", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables"]
    target = OUT / (source.stem + ".o")
    subprocess.run(compiler + ["-I" + str(ROOT / "arm_compat"), "-I" + str(ROOT / "vendor"), "-c", str(source), "-o", str(target)], check=True, cwd=ROOT)
    objects.append(target)
archive = OUT / "libdm1701-imbe-decoder-arm.a"
ar = shutil.which("llvm-ar") or shutil.which("ar")
if not ar:
    raise SystemExit("llvm-ar or ar is required")
subprocess.run([ar, "rcs", str(archive), *map(str, objects)], check=True)
print(f"{archive} ({archive.stat().st_size} bytes, {len(objects)} objects)")
