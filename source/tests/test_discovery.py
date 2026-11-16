import unittest
from types import SimpleNamespace
from unittest.mock import patch
from dm1701.discovery import native_lab_port

class NativeDiscoveryTests(unittest.TestCase):
    def test_single_native_lab_usb_is_found_without_opening_port(self):
        port=SimpleNamespace(vid=0x1fc9,pid=0x0094,device="COM7")
        with patch("serial.tools.list_ports.comports", return_value=[port]):
            self.assertEqual("COM7",native_lab_port())

    def test_unknown_or_multiple_devices_are_not_selected(self):
        port=SimpleNamespace(vid=0x1fc9,pid=0x0094,device="COM7")
        unrelated=SimpleNamespace(vid=0x1234,pid=0x0094,device="COM8")
        with patch("serial.tools.list_ports.comports", return_value=[unrelated]):
            self.assertIsNone(native_lab_port())
        with patch("serial.tools.list_ports.comports", return_value=[port,port]):
            self.assertIsNone(native_lab_port())
