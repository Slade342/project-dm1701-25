"""Lab firmware integrity and mocked receive-capture transactions; no USB access."""
import importlib.util
import io
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lab_capture", ROOT / "firmware-lab/capture.py")
capture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture_module)


class FakeRadio:
    def __init__(self):
        self.board = "DM-1701"
        self.mode = "fm"
        self.block = False
        self.writes = []
        self.fail_ram = False
        self.values = {}
    def version(self):
        return {"board": self.board, "git": "947c1398"}
    def view(self, sections):
        return {"mode": self.mode, "state": "rx", "rx_hz": "433450000", "txlim": "block" if self.block else "off"}
    def probe_status(self):
        return {"no_pcm": False}
    def tx_limit(self, block=False):
        self.block = block
    def probe_reg(self, page, register, value=None):
        if value is not None:
            self.writes.append((page, register, value))
            self.values[page, register] = value
            return value
        if page == 4 and register == 0x82:
            return 1
        return self.values.get((page, register), 0)
    def probe_ram(self, page, address, n):
        if self.fail_ram:
            raise OSError("simulated USB loss")
        return bytes(range(n))


class LabTests(unittest.TestCase):
    def clock(self):
        value = 0.0
        def now():
            nonlocal value
            value += 0.01
            return value
        return now

    def test_actual_image_hash_and_vectors(self):
        import hashlib, struct
        image = (ROOT / "firmware-lab/DM1701-CAPTURE-LAB.bin").read_bytes()
        meta = json.loads((ROOT / "firmware-lab/DM1701-CAPTURE-LAB.json").read_text())
        self.assertEqual("dm1701", meta["board"])
        self.assertEqual(meta["image"]["sha256"], hashlib.sha256(image).hexdigest())
        sp, entry = struct.unpack_from("<II", image)
        self.assertTrue(0x20000000 < sp < 0x20020000)
        self.assertTrue(entry & 1 and 0x0800C000 < entry < 0x080C0000)
        self.assertEqual("0x0800C000", meta["ranges"][0]["addr"])
        self.assertNotIn(0, meta["sectors"])
        self.assertNotIn(10, meta["sectors"])
        self.assertFalse(meta["codec"]["included"])

    def test_wrong_board_never_changes_hardware(self):
        radio = FakeRadio(); radio.board = "DM-32"
        with self.assertRaises(ValueError):
            capture_module.capture(radio, 0.1, lambda record: None, self.clock())
        self.assertFalse(radio.writes)
        self.assertFalse(radio.block)

    def test_dmr_mode_refused_before_register_writes(self):
        radio = FakeRadio(); radio.mode = "dmr"
        with self.assertRaises(ValueError):
            capture_module.capture(radio, 0.1, lambda record: None, self.clock())
        self.assertFalse(radio.writes)

    def test_records_restores_and_never_enables_tx(self):
        radio = FakeRadio(); records = []
        count = capture_module.capture(radio, 0.12, records.append, self.clock())
        self.assertGreater(count, 0)
        self.assertTrue(radio.block)
        self.assertEqual("header", records[0]["type"])
        self.assertEqual("summary", records[-1]["type"])
        self.assertTrue(records[-1]["register_restore"])
        self.assertEqual(72, len(next(record for record in records if record["type"] == "raw36")["hex"]))
        configured = next(record for record in records if record["type"] == "registers")
        self.assertEqual(2, configured["system"]["0x10"])
        self.assertEqual(0xD9, configured["system"]["0x08"])
        self.assertEqual(455000, configured["physical_test"]["if_hz_nominal"])
        for page, register, value in radio.writes:
            if page == 4 and register in (0x40, 0x41):
                self.assertFalse(value & 0x80)

    def test_usb_failure_still_restores_and_retains_error(self):
        radio = FakeRadio(); radio.fail_ram = True; records = []
        with self.assertRaises(OSError):
            capture_module.capture(radio, 0.12, records.append, self.clock())
        self.assertTrue(records[-1]["register_restore"])
        self.assertIn("USB loss", records[-1]["error"])
        self.assertTrue(radio.block)

    def test_capture_duration_bounded_before_access(self):
        radio = FakeRadio()
        with self.assertRaises(ValueError):
            capture_module.capture(radio, 31, lambda record: None)
        self.assertFalse(radio.writes)

    def test_no_data_ready_still_reports_buffer_and_register_diagnostics(self):
        radio = FakeRadio(); records = []
        original = radio.probe_reg
        def no_irq(page, register, value=None):
            if page == 4 and register == 0x82 and value is None:
                return 0
            return original(page, register, value)
        radio.probe_reg = no_irq
        self.assertEqual(0,capture_module.capture(radio,0.12,records.append,self.clock(),lambda _:None))
        self.assertTrue(any(r['type']=='registers' for r in records))
        self.assertTrue(any(r['type']=='ram_sample' for r in records))
        self.assertGreater(records[-1]['polls'],0)
        self.assertTrue(records[-1]['register_restore'])


if __name__ == "__main__":
    unittest.main()
