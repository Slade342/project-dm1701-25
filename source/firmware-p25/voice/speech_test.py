"""Desktop-only P25 Phase 1 IMBE playback test. No USB or RF operations."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import time
import wave

ROOT = Path(__file__).resolve().parent

def decode_to_wav(decoder, source, target, known=False):
    decoder,source,target=map(Path,(decoder,source,target))
    if source.resolve()==target.resolve():
        raise ValueError('Output must differ from the input capture.')
    if not decoder.is_file():
        raise ValueError('The desktop decoder executable is missing. Extract the complete speech-test update.')
    if source.suffix.lower() in ('.jsonl','.json','.wav','.iq'):
        raise ValueError('Use demodulated, packed on-air P25 bits. Raw C6000 JSONL, IQ and WAV need normalization/demodulation first.')
    with tempfile.TemporaryDirectory(prefix='p25-speech-') as folder:
        pcm=Path(folder)/'decoded.pcm'
        result=subprocess.run([str(decoder),'receive',str(source.resolve()),str(pcm)],capture_output=True,text=True,timeout=60)
        if result.returncode or not pcm.is_file():
            raise ValueError('No decodable P25 voice frames were found. '+result.stderr.strip())
        data=pcm.read_bytes()
    if not data or len(data)%320:
        raise ValueError('Decoder returned incomplete PCM audio.')
    peak=max(abs(sample[0]) for sample in struct.iter_unpack('<h',data))
    if peak==0:
        raise ValueError('Decoded output contains only silence; no clear voice was established.')
    target.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(target),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(8000);output.writeframes(data)
    report={'desktop_only':True,'radio_rx_tx_tested':False,'seconds':len(data)/16000,
            'voice_frames':len(data)//320,'peak':peak,'pcm_sha256':hashlib.sha256(data).hexdigest(),
            'output':str(target),'decoder_log':result.stderr.strip(),'known_fixture':known}
    if known:
        with wave.open(str(ROOT/'samples/reference-decoded.wav'),'rb') as reference:
            expected=reference.readframes(reference.getnframes())
        report['matches_reference_pcm']=data==expected
    target.with_suffix('.speech-test.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--known',action='store_true')
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--play',action='store_true')
    args=parser.parse_args()
    if not args.known and args.input is None:
        args.known=True
    source=ROOT/'samples/known-speech.p25bits' if args.known else args.input
    target=args.output or ROOT/'results'/('speech-'+time.strftime('%Y%m%d-%H%M%S')+'.wav')
    decoder=ROOT/'windows/p25-voice.exe' if sys.platform=='win32' else ROOT/'build/p25-voice'
    report=decode_to_wav(decoder,source,target,args.known)
    print(json.dumps(report,indent=2))
    if args.play:
        if sys.platform=='win32':
            import winsound
            winsound.PlaySound(str(target.resolve()),winsound.SND_FILENAME)
        else:
            print('Open the WAV file in an audio player.')
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('Speech test stopped: '+str(error),file=sys.stderr)
        raise SystemExit(1)
