"""Build the desktop decoder for Windows x64 using an installed Zig toolchain."""
from pathlib import Path
import os
import subprocess
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
(ROOT/'build').mkdir(exist_ok=True)
(ROOT/'windows').mkdir(exist_ok=True)
subprocess.run(['zig','cc','-target','x86_64-windows-gnu','-O2','-std=c11','-I../vendor/open25',
                '-c','../vendor/open25/p25.c','-o','build/p25-windows.o'],check=True)
subprocess.run(['zig','c++','-target','x86_64-windows-gnu','-O2','-std=c++14','-fwrapv',
                '-Ivendor','-I../vendor/open25','codec_cli.cc',
                *[str(p.relative_to(ROOT)) for p in sorted((ROOT/'vendor').glob('*.cc'))],
                'build/p25-windows.o','-o','windows/p25-voice.exe'],check=True)
