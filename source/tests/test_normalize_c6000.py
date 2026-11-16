import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("normalize_c6000", ROOT / "firmware-lab/normalize_c6000.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NormalizeC6000Tests(unittest.TestCase):
    def test_mapping_matches_arm_adapter(self):
        raw = bytes([0xB1]) + bytes(35)
        self.assertEqual(module.raw_to_dibits(raw, lsb_first=False, dibit_lsb_first=False, xor=0)[:4],
                         bytes([2, 3, 0, 1]))
        self.assertEqual(module.raw_to_dibits(raw, lsb_first=True, dibit_lsb_first=True, xor=2)[:4],
                         bytes([3, 2, 1, 0]))

    def test_jsonl_requires_contiguous_records_and_writes_dibits(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "capture.jsonl"
            source.write_text("\n".join([
                json.dumps({"type": "header", "mode": "physical-ber-continuous"}),
                json.dumps({"type": "raw36", "index": 0, "hex": ("00" * 36)}),
                json.dumps({"type": "raw36", "index": 1, "hex": ("ff" * 36)}),
            ]) + "\n", encoding="utf-8")
            records = module.read_records(source, False)
            self.assertEqual(2, len(records))
            out = root / "capture.dibits"
            out.write_bytes(b"".join(module.raw_to_dibits(r, lsb_first=False,
                                                            dibit_lsb_first=False, xor=0)
                                      for r in records))
            self.assertEqual(288, len(out.read_bytes()))


if __name__ == "__main__":
    unittest.main()
