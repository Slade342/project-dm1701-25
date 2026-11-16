import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
VOICE=ROOT/'firmware-p25/voice'
spec=importlib.util.spec_from_file_location('speech_playback',VOICE/'speech_test.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class SpeechPlaybackTests(unittest.TestCase):
    def test_raw_modem_json_is_not_treated_as_speech_bits(self):
        with self.assertRaisesRegex(ValueError,'normalization'):
            module.decode_to_wav(Path(__file__),Path('SAVE.jsonl'),Path('out.wav'))

    def test_input_is_never_overwritten(self):
        with self.assertRaisesRegex(ValueError,'differ'):
            module.decode_to_wav(Path(__file__),Path('same.bin'),Path('same.bin'))

    @unittest.skipUnless((VOICE/'build/p25-voice').exists(),'Native decoder needed for executable test')
    def test_real_known_speech_decodes_to_reference_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'decoded.wav'
            report=module.decode_to_wav(VOICE/'build/p25-voice',VOICE/'samples/known-speech.p25bits',target,True)
            self.assertEqual(261,report['voice_frames'])
            self.assertTrue(report['matches_reference_pcm'])
            self.assertTrue(target.with_suffix('.speech-test.json').is_file())
