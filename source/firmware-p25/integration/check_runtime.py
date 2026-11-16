#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host-check the exact linked receiver source with the real IMBE codec."""
from pathlib import Path
import argparse
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def run(args):
    subprocess.run(list(map(str,args)),check=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree',type=Path,default=Path('/workspace/work/dm1701-voice-derivative'))
    args=parser.parse_args()
    p25=ROOT/'firmware-p25';voice=p25/'voice';out=p25/'build/runtime';out.mkdir(parents=True,exist_ok=True)
    run(['make','-C',voice,'all'])
    includes=['-I'+str(HERE/'tests'),'-I'+str(args.tree/'core'),'-I'+str(args.tree/'hal'),'-I'+str(p25/'vendor/open25')]
    run(['cc','-O2','-ffunction-sections','-fdata-sections',*includes,'-c',HERE/'tests/test_runtime.c','-o',out/'test.o'])
    run(['c++','-O2','-fwrapv','-DSTUDIO_HOST_CODEC','-I'+str(voice/'vendor'),'-c',voice/'arm/p25_imbe_arm.cc','-o',out/'codec.o'])
    run(['cc','-O2','-I'+str(args.tree/'core'),'-c',args.tree/'core/debuglink/dl_fmt.c','-o',out/'fmt.o'])
    objects=[voice/'build'/(source.stem+'.o') for source in sorted((voice/'vendor').glob('*.cc'))]
    run(['c++','-Wl,--gc-sections',out/'test.o',out/'codec.o',out/'fmt.o',*objects,voice/'build/p25.o','-o',out/'test'])
    data=(voice/'samples/known-speech.p25bits').read_bytes()
    with tempfile.TemporaryDirectory(prefix='studio-mappings-') as temp:
        for mapping in range(8):
            transformed=bytearray(len(data))
            for i,byte in enumerate(data):
                for symbol,shift in enumerate((6,4,2,0)):
                    value=((byte>>shift)&3)^(2 if mapping&1 else 0)
                    a,b=(value&1,value>>1) if mapping&2 else (value>>1,value&1)
                    for bit,level in ((2*symbol,a),(2*symbol+1,b)):
                        transformed[i]|=level<<(bit if mapping&4 else 7-bit)
            candidate=Path(temp)/f'mapping-{mapping}.bin';candidate.write_bytes(transformed)
            run([out/'test',candidate])
    print('All eight raw C6000 mapping candidates recovered real reference speech through the actual receiver source.')

if __name__=='__main__':main()
