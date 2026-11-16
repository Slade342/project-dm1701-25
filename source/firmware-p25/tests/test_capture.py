# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the actual capture executable against independent OP25 vectors."""
from pathlib import Path
import json
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'build/p25-capture'
DATA=(ROOT/'tests/protocol/vectors/clear-call.bin').read_bytes()

def decode(data,*args):
    return subprocess.run([str(EXE),*args,'-'],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

result=decode(DATA,'--packed','--nac','293')
assert result.returncode==0, result.stderr
frames=[json.loads(x) for x in result.stdout.splitlines()]
assert [x['duid'] for x in frames]==[0,5,10,3]
assert frames[0]['talkgroup']==123 and frames[1]['source_id']==123456
assert all(x['nac']=='293' for x in frames)
assert frames[1]['imbe_channel_frames']==frames[2]['imbe_channel_frames']==9
assert json.loads(result.stderr)['radio_qualified'] is False
inverted=decode(bytes(x^0xaa for x in DATA))
assert inverted.returncode==0 and inverted.stdout==result.stdout
wrong=decode(DATA,'--nac','123')
assert wrong.returncode==1 and not wrong.stdout
invalid=decode(bytes([0,1,2,3,4]),'--dibits')
assert invalid.returncode==2
assert decode(b'').returncode==1
assert decode(DATA,'--nac','1000').returncode==2
assert decode(DATA,'--sync-errors','5').returncode==2
dibits=bytes((x>>shift)&3 for x in DATA for shift in (6,4,2,0))
assert decode(dibits,'--dibits').stdout==result.stdout
print('PASS capture CLI: OP25 fixture, inverted polarity, NAC filtering, input validation, packed/dibit equivalence')
