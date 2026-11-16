"""User-flow checks; GUI cases run when a display is available."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from dm1701.app import ChannelDialog, Studio
from dm1701.model import Codeplug, TaggedScalar


class ToneFormTests(unittest.TestCase):
    def test_tone_display_keeps_unsupported_dcs_opaque(self):
        self.assertEqual("88.5", ChannelDialog._tone_display({"ctcss": "88.5 Hz"}))
        self.assertEqual("", ChannelDialog._tone_display(None))
        self.assertEqual("[preserve existing tone]", ChannelDialog._tone_display({"dcs": -754}))

    def test_explicit_ctcss_change_emits_qdmr_mapping(self):
        self.assertEqual({"ctcss": "88.5 Hz"}, ChannelDialog._ctcss("88.5"))
        self.assertIsNone(ChannelDialog._ctcss(""))
        for value in ("nan", "inf", "60", "300", "{'dcs': 23}"):
            with self.assertRaises(ValueError):
                ChannelDialog._ctcss(value)


@unittest.skipUnless(os.environ.get("DISPLAY") or os.sys.platform == "darwin", "GUI needs a display")
class StudioFlowTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.studio = Studio(self.root)
        self.errors = patch("dm1701.app.messagebox.showerror").start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.root.destroy)

    def dialog(self, channel=None):
        result = ChannelDialog(self.studio, channel)
        self.addCleanup(lambda: result.window.destroy() if result.window.winfo_exists() else None)
        return result

    def test_editor_works_without_installed_radio_backend(self):
        self.assertEqual([], self.studio.document.channels())
        self.assertFalse(self.studio.busy)
        self.assertEqual("Choose installed firmware...", self.studio.profile.get())
        self.assertFalse(self.studio.confirm_model.get())

    def test_automatic_backup_open_requires_save_as(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "backup.yaml"
            Codeplug.new().save(path)
            original = path.read_bytes()
            self.studio._load_path(path, detach=True)
            self.assertIsNone(self.studio.path)
            self.assertEqual(original, path.read_bytes())

    def test_default_radio_identity_is_displayed(self):
        self.studio.document.set_radio_id(1234567, "Primary")
        self.studio.document.data["radioIDs"].insert(0, {"dmr": {"id": "other", "name": "Other", "number": 7654321}})
        self.studio._render()
        self.assertEqual("1234567", self.studio.radio_id.get())

    def test_keyboard_save_does_not_run_during_transfer(self):
        self.studio.busy = True
        with patch("dm1701.app.filedialog.asksaveasfilename") as save_dialog:
            self.assertFalse(self.studio._save())
            save_dialog.assert_not_called()

    def test_automatic_discovery_updates_connection_and_initial_profile(self):
        self.studio.discovery_queue.put((True, ("opengd77", "Open MD-UV380")))
        self.studio.discovering = True
        self.studio._poll()
        self.assertFalse(self.studio.discovering)
        self.assertEqual("OpenGD77 / OpenDM1701", self.studio.profile.get())
        self.assertIn("connected", self.studio.detected_status.get())

    def test_add_receive_only_channel_then_save_and_reopen(self):
        dialog = self.dialog()
        dialog.fields["name"].set("Local FM")
        dialog._apply()
        self.errors.assert_not_called()
        row = self.studio.document.channels()[0]
        self.assertEqual("FM", row.mode)
        self.assertTrue(row.rx_only)
        self.assertEqual([row.id], self.studio.document.data["zones"][0]["A"])
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "program.yaml"
            self.studio.path = target
            self.assertTrue(self.studio._save())
            self.assertEqual(self.studio.document.data, Codeplug.load(target).data)

    def test_rename_preserves_dcs_ctcss_inherited_power_and_extensions(self):
        doc = self.studio.document
        ident = doc.upsert_channel({"mode": "FM", "name": "Original", "rx_frequency": "145.5"})
        ch = doc.data["channels"][0]["fm"]
        ch.update({"rxTone": {"dcs": -754}, "txTone": {"ctcss": "88.5 Hz"},
                   "power": TaggedScalar("!default", ""), "vendorExtension": {"opaque": 42}})
        doc.data["vendorExtension"] = {"future": [1, 2, 3]}
        expected = deepcopy(ch)
        self.studio._render()
        dialog = self.dialog(self.studio.document.channels()[0])
        self.assertEqual("[preserve existing tone]", dialog.fields["rx_tone"].get())
        self.assertEqual("88.5", dialog.fields["tx_tone"].get())
        dialog.fields["name"].set("Renamed")
        dialog._apply()
        self.errors.assert_not_called()
        actual = self.studio.document.data["channels"][0]["fm"]
        for field in ("rxTone", "txTone", "power", "vendorExtension"):
            self.assertEqual(expected[field], actual[field], field)
        self.assertEqual({"future": [1, 2, 3]}, self.studio.document.data["vendorExtension"])
        self.assertEqual(ident, actual["id"])

    def test_explicit_tone_change_and_disable(self):
        self.studio.document.upsert_channel({"mode": "FM", "name": "FM", "rx_frequency": "145.5",
                                              "rx_tone": {"ctcss": "88.5 Hz"}, "tx_tone": {"dcs": 23}})
        self.studio._render()
        dialog = self.dialog(self.studio.document.channels()[0])
        dialog.fields["rx_tone"].set("")
        dialog.fields["tx_tone"].set("100.0")
        dialog._apply()
        self.errors.assert_not_called()
        actual = self.studio.document.data["channels"][0]["fm"]
        self.assertIsNone(actual["rxTone"])
        self.assertEqual({"ctcss": 100.0}, actual["txTone"])

    def test_invalid_form_does_not_mutate_document(self):
        before = self.studio.document.dumps()
        dialog = self.dialog()
        dialog.fields["rx_frequency"].set("200")
        dialog._apply()
        self.errors.assert_called_once()
        self.assertEqual(before, self.studio.document.dumps())
        self.assertTrue(dialog.window.winfo_exists())

    def test_missing_dmr_identity_allows_editing_but_blocks_program_snapshot(self):
        dialog = self.dialog()
        dialog.fields["name"].set("DMR RX")
        dialog.fields["mode"].set("DMR")
        dialog.fields["rx_frequency"].set("433.450")
        dialog.fields["tx_frequency"].set("433.450")
        dialog._apply()
        self.errors.assert_not_called()
        self.assertEqual("DMR", self.studio.document.channels()[0].mode)
        with self.assertRaisesRegex(ValueError, "assigned DMR radio ID"):
            self.studio._validated_snapshot()

    def test_p25_form_uses_yes_no_and_hides_dmr_fields(self):
        self.studio.document.upsert_channel({"mode": "P25", "name": "P25 RX", "rx_frequency": "443.25",
                                            "tx_frequency": "443.25", "nac": "293", "talkgroup": "1",
                                            "audio": True, "promiscuous": True, "rx_only": True})
        dialog = self.dialog(self.studio.document.channels()[0])
        self.assertEqual("Yes", dialog.fields["audio"].get())
        self.assertEqual("Yes", dialog.fields["promiscuous"].get())
        self.assertEqual("", dialog.field_rows["color_code"][1].winfo_manager())
        dialog.fields["name"].set("P25 edited")
        dialog._apply()
        self.errors.assert_not_called()
        channel = self.studio.document.channels()[0]
        self.assertEqual("P25", channel.mode)
        self.assertEqual(0x293, channel.nac)

    def test_usb_access_requires_profile_and_physical_model_confirmation(self):
        with self.assertRaisesRegex(ValueError, "Choose the firmware"):
            self.studio._get_profile(usb=True)
        self.studio.profile.set("OpenGD77 / OpenDM1701")
        with self.assertRaisesRegex(ValueError, "Confirm the physical"):
            self.studio._get_profile(usb=True)
        self.studio.confirm_model.set(True)
        self.assertEqual("opengd77", self.studio._get_profile(usb=True))


if __name__ == "__main__":
    unittest.main()
