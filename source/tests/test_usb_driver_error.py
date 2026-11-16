"""A driver failure must stop bootloader checks, never bypass them."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'firmware-lab/vendor'))
from rfoundry import dfu

class DriverErrorTests(unittest.TestCase):
    def test_unsupported_windows_driver_has_actionable_error(self):
        def unsupported(*args):
            raise NotImplementedError('Operation not supported')
        usb=SimpleNamespace(util=SimpleNamespace(get_string=unsupported))
        with self.assertRaises(dfu.DfuError) as error:
            dfu._string(usb,object(),1)
        self.assertIn('driver',str(error.exception))
