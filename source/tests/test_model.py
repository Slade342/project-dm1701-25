import tempfile
import unittest
from pathlib import Path
from dm1701.model import Codeplug, ModelError, TaggedScalar, frequency_mhz, parse_tone, format_tone
from unittest.mock import patch


class ModelTests(unittest.TestCase):
    def fm(self):
        doc = Codeplug.new()
        ch = doc.upsert_channel({"mode": "FM", "name": "Listen", "rx_frequency": "145.500", "tx_frequency": "145.500", "rx_only": True})
        return doc, ch

    def dmr(self):
        doc = Codeplug.new()
        doc.set_radio_id(1234567, "My radio")
        ch = doc.upsert_channel({"mode": "DMR", "name": "DMR RX", "rx_frequency": "433.450", "tx_frequency": "433.450", "rx_only": True, "color_code": 1, "time_slot": "TS2", "contact": "tg9"})
        return doc, ch

    def test_new_is_valid_without_fake_identity(self):
        doc = Codeplug.new()
        self.assertEqual([], doc.validate())
        self.assertEqual([], doc.data["radioIDs"])

    def test_new_channel_added_to_zone_and_receive_only(self):
        doc, ch = self.fm()
        self.assertEqual([ch], doc.data["zones"][0]["A"])
        self.assertTrue(doc.channels()[0].rx_only)
        self.assertEqual([], doc.validate())

    def test_dmr_schema_matches_qdmr_and_validates(self):
        doc, ch = self.dmr()
        self.assertIn("dmr", doc.data["channels"][0])
        self.assertEqual("TS2", doc.channels()[0].time_slot)
        self.assertEqual([], doc.validate())

    def test_dmr_requires_explicit_radio_identity(self):
        doc = Codeplug.new()
        doc.upsert_channel({"mode": "DMR", "name": "DMR RX", "rx_frequency": "433.450", "color_code": 1, "time_slot": "TS1"})
        self.assertTrue(any("assigned DMR radio ID" in e for e in doc.validate()))

    def test_unknown_extension_and_tags_survive_edit(self):
        doc, ch = self.fm()
        loaded = Codeplug.loads(doc.dumps() + "vendorExtension:\n  obscureSetting: 42\n  power: !<!default> ''\n")
        loaded.upsert_channel({"mode": "FM", "name": "Changed", "rx_frequency": "145.600", "tx_frequency": "145.600"}, ch)
        again = Codeplug.loads(loaded.dumps())
        self.assertEqual(42, again.data["vendorExtension"]["obscureSetting"])
        self.assertEqual(TaggedScalar("!default", ""), again.data["vendorExtension"]["power"])

    def test_channel_unknown_fields_and_contact_survive_edit(self):
        doc, ch = self.dmr()
        doc.data["channels"][0]["dmr"]["vendorExtension"] = {"flag": True}
        doc.upsert_channel({"mode": "DMR", "name": "Changed", "rx_frequency": "433.500"}, ch)
        self.assertEqual({"flag": True}, doc.data["channels"][0]["dmr"]["vendorExtension"])
        self.assertEqual("tg9", doc.channels()[0].contact)

    def test_duplicate_yaml_keys_rejected(self):
        with self.assertRaises(ModelError):
            Codeplug.loads("channels: []\nchannels: []\n")

    def test_alias_and_unsafe_python_tag_rejected(self):
        for text in ("a: &x [1]\nb: *x\n", "a: !!python/object/apply:os.system [echo BAD]\n"):
            with self.assertRaises(ModelError):
                Codeplug.loads(text)

    def test_p25_channel_is_preserved_for_experimental_workbench(self):
        doc = Codeplug.loads("channels:\n- p25:\n    id: p1\n    name: P25\n    rxFrequency: 145.5\n    txFrequency: 145.5\n    nac: 659\n")
        self.assertEqual("P25", doc.channels()[0].mode)
        self.assertFalse(any("P25 is not implemented" in e for e in doc.validate()))
        doc.upsert_channel({"mode": "P25", "name": "P25", "rx_frequency": 145.5, "tx_frequency": 145.5})
        self.assertFalse(doc.validate())
        self.assertIn("p25:", doc.dumps())

    def test_invalid_frequencies_rejected(self):
        doc, ch = self.fm()
        for value in ("nan", "inf", "145.500001 MHz", "200 MHz", True):
            doc.data["channels"][0]["fm"]["rxFrequency"] = value
            self.assertTrue(doc.validate(), value)
        self.assertEqual(frequency_mhz("145500 kHz"), frequency_mhz("145.500 MHz"))

    def test_invalid_color_slot_and_dangling_contact(self):
        doc, ch = self.dmr()
        item = doc.data["channels"][0]["dmr"]
        item.update({"colorCode": 16, "timeSlot": "TS3", "contact": "missing"})
        errors = doc.validate()
        self.assertTrue(any("colorCode" in e for e in errors))
        self.assertTrue(any("timeSlot" in e for e in errors))
        self.assertTrue(any("unknown DMR contact" in e for e in errors))

    def test_remove_channel_cleans_memberships(self):
        doc, ch = self.fm()
        doc.data["scanLists"].append({"id": "scan1", "name": "Scan", "channels": [ch]})
        doc.remove_channel(ch)
        self.assertEqual([], doc.data["zones"][0]["A"])
        self.assertEqual([], doc.data["scanLists"][0]["channels"])
        self.assertEqual([], doc.channels())

    def test_remove_rejects_priority_and_unknown_extension_refs(self):
        doc, ch = self.fm()
        doc.data["scanLists"].append({"id": "scan1", "name": "Scan", "channels": [ch], "primary": ch})
        with self.assertRaises(ModelError):
            doc.remove_channel(ch)
        self.assertEqual(1, len(doc.channels()))

    def test_duplicate_id_and_dangling_zone_rejected(self):
        doc, ch = self.fm()
        doc.data["zones"].append({"id": "zone1", "name": "Another", "A": ["missing"], "B": []})
        errors = doc.validate()
        self.assertTrue(any("Duplicate object id" in e for e in errors))
        self.assertTrue(any("unknown channel" in e for e in errors))

    def test_contact_edit_preserves_reference(self):
        doc, ch = self.dmr()
        doc.upsert_contact(91, "World", "tg9")
        self.assertEqual("tg9", doc.channels()[0].contact)
        self.assertEqual(91, doc.data["contacts"][0]["dmr"]["number"])
        self.assertEqual([], doc.validate())

    def test_file_roundtrip_and_utf8(self):
        doc, ch = self.fm()
        doc.data["channels"][0]["fm"]["name"] = "München"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "radio.yaml"
            doc.save(target)
            self.assertEqual(doc.data, Codeplug.load(target).data)

    def test_tone_forms_emit_qdmr_mapping(self):
        doc, ch = self.fm()
        doc.upsert_channel({"mode": "FM", "name": "Listen", "rx_frequency": 145.5,
                            "rx_tone": "88.5", "tx_tone": "D023N"}, ch)
        item = doc.data["channels"][0]["fm"]
        self.assertEqual({"ctcss": 88.5}, item["rxTone"])
        self.assertEqual({"dcs": "n023"}, item["txTone"])
        self.assertEqual({"dcs": "i023"}, parse_tone("DCS i023"))
        self.assertIsNone(parse_tone("Off"))
        self.assertEqual("88.5", format_tone(item["rxTone"]))
        with self.assertRaises(ModelError):
            parse_tone("D089N")

    def test_name_edit_preserves_imported_tone_mapping(self):
        doc, ch = self.fm()
        doc.data["channels"][0]["fm"]["rxTone"] = {"dcs": "i037"}
        doc.upsert_channel({"mode": "FM", "name": "Changed", "rx_frequency": 145.5}, ch)
        self.assertEqual({"dcs": "i037"}, doc.data["channels"][0]["fm"]["rxTone"])

    def test_save_failure_preserves_existing_file(self):
        doc, ch = self.fm()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "radio.yaml"
            target.write_text("old bytes", encoding="utf-8")
            with patch("dm1701.model.os.replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    doc.save(target)
            self.assertEqual("old bytes", target.read_text(encoding="utf-8"))
            self.assertEqual([target], list(Path(tmp).iterdir()))

    def test_malformed_ids_and_reference_types_report_errors(self):
        doc, ch = self.dmr()
        doc.data["channels"][0]["dmr"]["contact"] = {"unexpected": "mapping"}
        self.assertTrue(doc.validate())
        doc.data["channels"][0]["dmr"]["id"] = ["invalid"]
        self.assertTrue(doc.validate())


    def test_mode_change_removes_inapplicable_known_fields(self):
        doc, ch = self.dmr()
        doc.upsert_channel({"mode": "FM", "name": "FM", "rx_frequency": 145.5, "tx_frequency": 145.5}, ch)
        self.assertNotIn("colorCode", doc.data["channels"][0]["fm"])
        self.assertEqual([], doc.validate())


if __name__ == "__main__":
    unittest.main()
