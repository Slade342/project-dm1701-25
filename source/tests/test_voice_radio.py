"""Native P25 receiver CLI contract; no physical radio is opened."""
import importlib.util
from pathlib import Path
import struct
import unittest

SPEC = importlib.util.spec_from_file_location("voice_radio", Path(__file__).resolve().parents[1] / "firmware-voice/radio.py")
radio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(radio)


class Link:
    def __init__(self, protocol="dm1701-p25/1"):
        self.commands = []
        self.protocol = protocol

    def request(self, command, payload):
        self.commands.append((command, payload))
        if payload == b"\x00":
            return 0, f"protocol={self.protocol} board=DM-1701 rx_hz=443250000 enabled=1".encode()
        return 0, b"queued=1"


class VoiceRadioTests(unittest.TestCase):
    def test_status_only_performs_one_read(self):
        link = Link()
        result = radio.configure(link)
        self.assertEqual("443250000", result["rx_hz"])
        self.assertEqual([(0x30, b"\x00")], link.commands)

    def test_tune_contract_preserves_frequency_and_nac(self):
        link = Link()
        result = radio.configure(link, frequency="154.23500", nac="293", enable=True)
        self.assertEqual((154235000, 0x293, 1, 255), struct.unpack("<IHBB", link.commands[-1][1][1:]))
        self.assertFalse(result["rf_reception_verified"])

    def test_wrong_firmware_cannot_receive_configuration(self):
        link = Link("other")
        with self.assertRaisesRegex(ValueError, "matching voice image"):
            radio.configure(link, frequency="443.25", enable=True)
        self.assertEqual(1, len(link.commands))

    def test_frequency_and_nac_reject_invalid_inputs(self):
        for value in ("nan", "inf", "850", "200", "443.2500001", "-1"):
            with self.assertRaises(ValueError):
                radio.frequency_hz(value)
        for value in ("1000", "-1", "hello"):
            with self.assertRaises(ValueError):
                radio.nac_value(value)
        self.assertEqual(0xFFFF, radio.nac_value("any"))


if __name__ == "__main__":
    unittest.main()
