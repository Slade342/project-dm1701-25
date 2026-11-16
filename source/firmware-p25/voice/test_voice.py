# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise actual PCM -> IMBE -> P25 frames -> streaming RX -> PCM."""
import array, math, pathlib, subprocess, sys, tempfile
root=pathlib.Path(__file__).resolve().parent
def run(args):
 result=subprocess.run([str(x) for x in args],capture_output=True)
 assert result.returncode==0,result.stderr.decode()
 return result
with tempfile.TemporaryDirectory() as folder:
 p=pathlib.Path(folder)
 # 18 speech-codec frames = two complete LDUs, including the encoder's initial latency.
 samples=array.array('h',(int(9000*math.sin(2*math.pi*440*n/8000)) for n in range(18*160)))
 if sys.byteorder!='little':samples.byteswap()
 (p/'in.pcm').write_bytes(samples.tobytes())
 run([root/'build/p25-voice','encode',p/'in.pcm',p/'voice.be16'])
 assert (p/'voice.be16').stat().st_size==18*16
 run([root/'../build/p25-txfile','--imbe',p/'voice.be16','--out',p/'call.bin','--nac','293','--tg','123','--id','123456'])
 assert (p/'call.bin').stat().st_size==99+216*2+18
 run([root/'build/p25-voice','receive',p/'call.bin',p/'out.pcm'])
 assert (p/'out.pcm').stat().st_size==18*320
 out=array.array('h');out.frombytes((p/'out.pcm').read_bytes())
 if sys.byteorder!='little':out.byteswap()
 # Establish audio exists and the stateful codec stays bounded, not perceptual quality.
 assert max(abs(n) for n in out)>100
 run([root/'build/p25-voice','decode',p/'voice.be16',p/'direct.pcm'])
 assert (p/'direct.pcm').stat().st_size==18*320
 # Truncated PCM is rejected instead of inventing the final audio frame.
 (p/'bad.pcm').write_bytes(b'\0')
 assert subprocess.run([str(root/'build/p25-voice'),'encode',str(p/'bad.pcm'),str(p/'bad.vec')],capture_output=True).returncode!=0
 assert not (p/'bad.vec').exists()
 print('PASS actual PCM/IMBE encoder, P25 call assembly, stream FEC and IMBE speech decode; malformed input rejected')
