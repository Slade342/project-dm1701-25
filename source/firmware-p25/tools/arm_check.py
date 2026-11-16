#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile portable protocol/probe objects for the DM-1701 Cortex-M4, no link/flash."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--zig',help='Path to a Zig executable for a freestanding cross-check')
args=ap.parse_args()
if args.zig:
    command=[args.zig,'cc','-target','thumb-freestanding-eabi','-mcpu=cortex_m4']
elif shutil.which('arm-none-eabi-gcc'):
    command=['arm-none-eabi-gcc','-mcpu=cortex-m4','-mthumb','-mfloat-abi=soft']
elif shutil.which('clang'):
    command=['clang','--target=arm-none-eabi','-mcpu=cortex-m4','-mthumb','-mfloat-abi=soft']
else:
    ap.exit(2,'No ARM C compiler found. Install Arm GNU Toolchain, LLVM clang, or pass --zig /path/to/zig.\n')
out=ROOT/'build/arm'
out.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('ZIG_GLOBAL_CACHE_DIR',str(ROOT/'build/zig-cache'))
os.environ.setdefault('ZIG_LOCAL_CACHE_DIR',str(ROOT/'build/zig-local'))
common=['-std=c11','-ffreestanding','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror','-pedantic','-Os','-fdata-sections','-ffunction-sections','-I'+str(ROOT/'vendor/open25'),'-I'+str(ROOT/'src'),'-I'+str(ROOT/'vendor/radiofoundry')]
records=[]
for source,name,flags in [('vendor/open25/p25.c','p25.o',[]),('src/p25_audio_pipeline.c','p25-audio-pipeline.o',[]),('src/dm1701_c6000_adapter.c','c6000-symbol-adapter.o',[]),('src/p25_speaker_fifo.c','p25-speaker-fifo.o',[]),('src/dm1701_rx_probe.c','probe-disabled.o',[]),('src/dm1701_rx_probe.c','probe-experimental.o',['-DDM1701_EXPERIMENTAL_RX=1']),('src/radiofoundry_bridge.c','radiofoundry-bridge.o',[])]:
    target=out/name
    subprocess.run(command+common+flags+['-c',str(ROOT/source),'-o',str(target)],check=True,cwd=ROOT)
    data=target.read_bytes()
    assert data[:4]==b'\x7fELF' and data[4]==1 and data[5]==1
    assert struct.unpack_from('<H',data,18)[0]==40, 'Output is not ARM ELF'
    records.append({'source':source,'object':str(target.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'machine':'ARM','linked':False})
version=subprocess.check_output(command[:2]+['--version'] if args.zig else command[:1]+['--version'],text=True).splitlines()[0]
report={'compiler':version,'target':'Cortex-M4 / Thumb, freestanding','objects':records,'radio_qualified':False,'firmware_image_generated':False}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
