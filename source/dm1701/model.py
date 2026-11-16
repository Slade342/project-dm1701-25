"""Conservative DM-1701 editor for qdmr YAML (semantic round trips).

Schema: https://github.com/hmatuschek/qdmr/tree/master/examples
Unknown settings/extensions survive editing. Comments/formatting do not.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import tempfile
import re
from typing import Any
import yaml


class ModelError(ValueError):
    pass


@dataclass(frozen=True)
class TaggedScalar:
    tag: str
    value: str


class _Loader(yaml.SafeLoader):
    """Safe YAML with duplicate keys and aliases rejected, not silently changed."""

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise ModelError("YAML aliases are not supported; expand aliases before editing.")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in result:
                    raise ModelError(f"Duplicate YAML key: {key}")
                result[key] = self.construct_object(value_node, deep=deep)
            except TypeError as exc:
                raise ModelError("YAML mapping keys must be scalar values.") from exc
        return result


class _Dumper(yaml.SafeDumper):
    pass


def _tagged(loader, tag_suffix, node):
    if not isinstance(node, yaml.ScalarNode):
        raise ModelError(f"Unsupported structured YAML tag: !{tag_suffix}")
    if tag_suffix not in ("default", "selected"):
        raise ModelError(f"Unsupported YAML tag: !{tag_suffix}")
    return TaggedScalar("!" + tag_suffix, loader.construct_scalar(node))


def _represent_tagged(dumper, value):
    return dumper.represent_scalar(value.tag, value.value)


_Loader.add_multi_constructor("!", _tagged)
_Dumper.add_representer(TaggedScalar, _represent_tagged)


def frequency_mhz(value: Any) -> Decimal:
    """qdmr accepts MHz numbers or a string such as '145.500 MHz'."""
    if isinstance(value, bool):
        raise ModelError("Frequency must be a number in MHz.")
    text = str(value).strip()
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(MHz|kHz|Hz)?", text, re.I)
    if not match:
        raise ModelError(f"Invalid frequency: {value!r}")
    try:
        result = Decimal(match.group(1))
    except InvalidOperation as exc:
        raise ModelError("Frequency must be finite.") from exc
    unit = (match.group(2) or "MHz").lower()
    return result / {"mhz": Decimal(1), "khz": Decimal(1000), "hz": Decimal(1000000)}[unit]


def _frequency_text(value: Any) -> str:
    number = frequency_mhz(value)
    return f"{number:f} MHz"


def _contains(container, value) -> bool:
    try:
        return value in container
    except TypeError:
        return False


def parse_tone(value: Any):
    """Convert form text to qdmr's null / {ctcss: Hz} / {dcs: n023} schema."""
    if value is None or isinstance(value, TaggedScalar):
        return deepcopy(value)
    if isinstance(value, dict):
        if len(value) != 1 or not any(key in value for key in ("ctcss", "dcs")):
            raise ModelError("Tone must contain one ctcss or dcs field.")
        if "ctcss" in value:
            return parse_tone(value["ctcss"])
        if isinstance(value["dcs"], int) and not isinstance(value["dcs"], bool):
            digits = f'{value["dcs"]:03d}'
            if re.fullmatch(r"[0-7]{3}", digits):
                return {"dcs": "n" + digits}
            raise ModelError("DCS code must have three octal digits.")
        return parse_tone(value["dcs"])
    text = str(value).strip()
    if text.lower() in ("", "off", "none", "-", "null"):
        return None
    match = re.fullmatch(r"(?:CTCSS\s*)?(\d+(?:\.\d+)?)\s*(?:Hz)?", text, re.I)
    if match:
        number = Decimal(match.group(1))
        if not Decimal(50) <= number <= Decimal(300):
            raise ModelError("CTCSS tone must be between 50 and 300 Hz.")
        return {"ctcss": float(number)}
    match = re.fullmatch(r"(?:DCS\s*)?([ni])([0-7]{3})", text, re.I)
    if match:
        return {"dcs": match.group(1).lower() + match.group(2)}
    match = re.fullmatch(r"D([0-7]{3})([NI])", text, re.I)
    if match:
        return {"dcs": match.group(2).lower() + match.group(1)}
    raise ModelError("Use a CTCSS tone such as 88.5, DCS such as n023/i023, or leave blank.")


def format_tone(value: Any) -> str:
    """Display a qdmr tone without changing the underlying imported object."""
    if value is None:
        return ""
    if isinstance(value, dict) and len(value) == 1:
        if "ctcss" in value:
            return str(value["ctcss"])
        if "dcs" in value:
            return str(value["dcs"])
    if isinstance(value, TaggedScalar):
        return value.tag
    return str(value)


def _integer(value: Any, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _plain_entries(data, name):
    entries = data.get(name, [])
    return entries if isinstance(entries, list) else []


def _wrapped(entries, allowed):
    for entry in entries:
        if isinstance(entry, dict):
            for key in allowed:
                if isinstance(entry.get(key), dict):
                    yield key, entry[key]
                    break


@dataclass(frozen=True)
class ChannelRow:
    id: str
    mode: str
    name: str
    rx_frequency: str
    tx_frequency: str
    rx_only: bool
    color_code: int | str = ""
    time_slot: str = ""
    contact: str = ""
    bandwidth: str = "Narrow"
    power: str = "Low"
    rx_tone: Any = None
    tx_tone: Any = None
    nac: int = 0
    talkgroup: int = 0
    audio: bool = True
    promiscuous: bool = False
    # P25 receiver admission policy.  This is a Project DM1701-25 extension and is
    # intentionally kept on the channel rather than hidden in a global flag:
    # a codeplug can mix ordinary NAC/TG filtering with an explicit no-filter
    # scan channel.
    scan_mode: str = "NAC + talkgroup"


class Codeplug:
    def __init__(self, data: dict):
        if not isinstance(data, dict):
            raise ModelError("A qdmr codeplug must contain a YAML mapping.")
        self.data = deepcopy(data)

    @classmethod
    def new(cls):
        return cls({
            "version": "0.12.0",
            "settings": {"introLine1": "DM-1701", "introLine2": "Studio", "power": "Low", "squelch": 3},
            "radioIDs": [],
            "contacts": [{"dmr": {"id": "tg9", "name": "Local TG9", "type": "GroupCall", "number": 9, "ring": False}}],
            "groupLists": [{"id": "gl9", "name": "Local receive", "contacts": ["tg9"]}],
            "channels": [], "zones": [], "scanLists": [],
        })

    @classmethod
    def parker_county(cls):
        """Receive-only NTIRN Parker County VHF template from RadioReference."""
        sites = [
            ("Main VHF", 0x441, [("152.060", True), ("152.540", True), ("152.720", True), ("154.725", True), ("154.875", False), ("155.385", False)]),
            ("Agnes VHF", 0x443, [("152.120", True), ("152.780", True), ("154.250", True), ("152.600", False), ("155.7375", False)]),
            ("Cool VHF", 0x444, [("152.810", True), ("155.7225", True), ("158.7825", True), ("152.585", False)]),
            ("Azle VHF", 0x447, [("152.180", True), ("152.810", True), ("152.600", False), ("155.490", False), ("159.3825", False)]),
            ("Vanguard VHF", 0x442, [("152.090", True), ("152.570", True), ("152.750", True), ("155.2575", False)]),
        ]
        channels, ids, scan = [], [], []
        for site, nac, frequencies in sites:
            for number, (frequency, control) in enumerate(frequencies, 1):
                ident = f"p{len(ids) + 1}"
                ids.append(ident)
                short_site = {"Main VHF": "Main", "Agnes VHF": "Agnes", "Cool VHF": "Cool", "Azle VHF": "Azle", "Vanguard VHF": "Vang"}[site]
                channels.append({"p25": {"id": ident, "name": f"{short_site} {'C' if control else 'V'}{number}",
                                          "rxFrequency": frequency, "txFrequency": frequency, "rxOnly": True,
                                          "nac": nac, "talkgroup": 1, "audio": True, "promiscuous": True,
                                          "scanMode": "NAC only",
                                          "scanList": "parker-vhf"}})
                if control:
                    scan.append(ident)
        ident = f"p{len(ids) + 1}"
        channels.append({"p25": {"id": ident, "name": "443.250 P25", "rxFrequency": "443.250", "txFrequency": "443.250",
                                  "rxOnly": True, "nac": 0x293, "talkgroup": 1, "audio": True, "promiscuous": True,
                                  "scanMode": "No filter",
                                  "scanList": "parker-vhf"}})
        ids.append(ident)
        return cls({"version": "0.12.0", "settings": {"introLine1": "DM-1701", "introLine2": "Parker P25", "power": "Low", "squelch": 3},
                    "radioIDs": [], "contacts": [], "groupLists": [], "channels": channels,
                    "zones": [{"id": "zone1", "name": "Parker P25", "A": ids, "B": []}],
                    "scanLists": [{"id": "parker-vhf", "name": "Parker VHF", "channels": scan}]})

    @classmethod
    def loads(cls, text: str):
        if len(text.encode("utf-8")) > 8 * 1024 * 1024:
            raise ModelError("Codeplug exceeds the 8 MB editor limit.")
        try:
            data = yaml.load(text, Loader=_Loader)
        except (yaml.YAMLError, RecursionError) as exc:
            raise ModelError(f"Invalid YAML: {exc}") from exc
        return cls(data)

    @classmethod
    def load(cls, path):
        return cls.loads(Path(path).read_text(encoding="utf-8-sig"))

    def dumps(self) -> str:
        return yaml.dump(self.data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100)

    def save(self, path):
        target = Path(path)
        # Keep the previous file intact if writing or replacing the new file fails.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                             prefix=f".{target.name}.", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(self.dumps())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def channels(self) -> list[ChannelRow]:
        rows = []
        for entry in _plain_entries(self.data, "channels"):
            if not isinstance(entry, dict) or len(entry) != 1:
                continue
            kind, ch = next(iter(entry.items()))
            if not isinstance(ch, dict):
                continue
            mode = {"fm": "FM", "dmr": "DMR", "digital": "DMR", "p25": "P25"}.get(kind, str(kind).upper())
            rows.append(ChannelRow(
                str(ch.get("id", "")), mode, str(ch.get("name", "")),
                str(ch.get("rxFrequency", "")), str(ch.get("txFrequency", "")),
                ch.get("rxOnly", False) is True, ch.get("colorCode", ""),
                str(ch.get("timeSlot", "")), str(ch.get("contact", "") or ""),
                str(ch.get("bandwidth", "Narrow")), str(ch.get("power", "Low")),
                ch.get("rxTone"), ch.get("txTone"), int(ch.get("nac", 0)), int(ch.get("talkgroup", 0)),
                ch.get("audio", True) is True, ch.get("promiscuous", False) is True,
                str(ch.get("scanMode", "NAC + talkgroup"))))
        return rows

    def _all_ids(self):
        found = set()
        def visit(obj):
            if isinstance(obj, dict):
                if isinstance(obj.get("id"), str):
                    found.add(obj["id"])
                for value in obj.values():
                    visit(value)
            elif isinstance(obj, list):
                for value in obj:
                    visit(value)
        visit(self.data)
        return found

    def _next_id(self, prefix):
        existing = self._all_ids()
        number = 1
        while f"{prefix}{number}" in existing:
            number += 1
        return f"{prefix}{number}"

    def upsert_channel(self, fields: dict, channel_id: str | None = None) -> str:
        mode = str(fields.get("mode", "FM")).upper()
        if mode not in ("FM", "DMR", "P25"):
            raise ModelError("Choose FM, DMR, or experimental P25.")
        table = self.data.setdefault("channels", [])
        if not isinstance(table, list):
            raise ModelError("channels must be a list.")
        old = None
        index = None
        old_kind = None
        if channel_id:
            for i, entry in enumerate(table):
                if not isinstance(entry, dict):
                    continue
                for kind, value in entry.items():
                    if isinstance(value, dict) and value.get("id") == channel_id:
                        old, index, old_kind = value, i, kind
                        break
            if old is None:
                raise ModelError(f"Channel {channel_id!r} was not found.")
        chosen_id = channel_id or self._next_id("ch")
        kind = "fm" if mode == "FM" else "p25" if mode == "P25" else "dmr"
        if old_kind == "digital" and mode == "DMR":
            kind = "digital"
        ch = deepcopy(old) if old else {}
        if old_kind and ((old_kind == "fm") != (kind == "fm")):
            for key in ("colorCode", "timeSlot", "contact", "groupList", "radioId", "rxTone", "txTone", "bandwidth", "squelch"):
                ch.pop(key, None)
        ch.update({
            "id": chosen_id, "name": str(fields.get("name", "Channel")),
            "rxFrequency": _frequency_text(fields.get("rx_frequency", "145.5")),
            "txFrequency": _frequency_text(fields.get("tx_frequency", fields.get("rx_frequency", "145.5"))),
            "rxOnly": fields.get("rx_only", True), "power": fields.get("power", ch.get("power", "Low")),
        })
        ch.setdefault("admit", "Always")
        if mode == "FM":
            ch["bandwidth"] = fields.get("bandwidth", ch.get("bandwidth", "Narrow"))
            for form_key, yaml_key in (("rx_tone", "rxTone"), ("tx_tone", "txTone")):
                if form_key in fields:
                    ch[yaml_key] = parse_tone(fields[form_key])
        elif mode == "DMR":
            if not old and any(isinstance(group, dict) and group.get("id") == "gl9" for group in self.data.get("groupLists", [])):
                ch.setdefault("groupList", "gl9")
            try:
                ch["colorCode"] = int(fields.get("color_code", ch.get("colorCode", 1)))
            except (ValueError, TypeError) as exc:
                raise ModelError("DMR color code must be an integer from 0 to 15.") from exc
            ch["timeSlot"] = fields.get("time_slot", ch.get("timeSlot", "TS1"))
            contact = fields.get("contact", ch.get("contact", "tg9"))
            if contact:
                ch["contact"] = contact
            else:
                ch.pop("contact", None)
        else:
            try:
                nac_text = str(fields.get("nac", ch.get("nac", "293"))).strip()
                ch["nac"] = 0xFFFF if nac_text.casefold() in ("any", "all", "ffff") else int(nac_text, 16)
                ch["talkgroup"] = int(fields.get("talkgroup", ch.get("talkgroup", 1)))
            except (ValueError, TypeError) as exc:
                raise ModelError("P25 NAC must be hexadecimal and talkgroup must be numeric.") from exc
            ch["audio"] = fields.get("audio", ch.get("audio", True))
            scan_mode = str(fields.get("scan_mode", ch.get("scanMode", "NAC + talkgroup")))
            if scan_mode not in ("NAC + talkgroup", "NAC only", "No filter"):
                raise ModelError("P25 scan mode must be NAC + talkgroup, NAC only, or No filter.")
            ch["scanMode"] = scan_mode
            # No-filter and NAC-only are receiver-side admission policies.  A
            # legacy `promiscuous` value remains in the YAML for compatibility,
            # but the clear choice in the CPS is scanMode.
            ch["promiscuous"] = scan_mode != "NAC + talkgroup" if "scan_mode" in fields else fields.get("promiscuous", ch.get("promiscuous", False))
            if scan_mode == "No filter":
                ch["nac"] = 0xFFFF
        if index is None:
            table.append({kind: ch})
            zones = self.data.setdefault("zones", [])
            if not isinstance(zones, list):
                table.pop()
                raise ModelError("zones must be a list.")
            if not zones:
                zones.append({"id": self._next_id("zone"), "name": "Channels", "A": [], "B": []})
            if not isinstance(zones[0], dict) or not isinstance(zones[0].setdefault("A", []), list):
                table.pop()
                raise ModelError("First zone must have a channel list A.")
            zones[0]["A"].append(chosen_id)
        else:
            table[index] = {kind: ch}
        return chosen_id

    def remove_channel(self, channel_id):
        """Remove a channel and its zone/scan memberships; reject other references."""
        def other_refs(obj, location=""):
            hits = []
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if location == "" and key in ("channels", "zones", "scanLists"):
                        continue
                    if key != "id" and value == channel_id:
                        hits.append(f"{location}.{key}".strip("."))
                    elif isinstance(value, (dict, list)):
                        hits.extend(other_refs(value, f"{location}.{key}".strip(".")))
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    if value == channel_id:
                        hits.append(f"{location}[{i}]")
                    elif isinstance(value, (dict, list)):
                        hits.extend(other_refs(value, f"{location}[{i}]"))
            return hits
        refs = other_refs(self.data)
        # Priority/selected TX references cannot just be removed from a scan list.
        for scan in _plain_entries(self.data, "scanLists"):
            if isinstance(scan, dict):
                for key, value in scan.items():
                    if key != "channels" and value == channel_id:
                        refs.append(f"scanLists.{scan.get('id', '?')}.{key}")
        if refs:
            raise ModelError("Channel is referenced by " + ", ".join(refs) + "; update those references first.")
        table = self.data.get("channels", [])
        kept = [entry for entry in table if not (isinstance(entry, dict) and any(isinstance(ch, dict) and ch.get("id") == channel_id for ch in entry.values()))]
        if len(kept) == len(table):
            raise ModelError(f"Channel {channel_id!r} was not found.")
        self.data["channels"] = kept
        for zone in _plain_entries(self.data, "zones"):
            if isinstance(zone, dict):
                for key in ("A", "B"):
                    if isinstance(zone.get(key), list):
                        zone[key] = [v for v in zone[key] if v != channel_id]
        for scan in _plain_entries(self.data, "scanLists"):
            if isinstance(scan, dict) and isinstance(scan.get("channels"), list):
                scan["channels"] = [v for v in scan["channels"] if v != channel_id]

    def set_radio_id(self, number: int, name="My radio"):
        if not _integer(number, 1, 16777215):
            raise ModelError("DMR radio ID must be an integer from 1 to 16777215.")
        settings = self.data.setdefault("settings", {})
        entries = self.data.setdefault("radioIDs", [])
        if not isinstance(settings, dict) or not isinstance(entries, list):
            raise ModelError("settings must be a mapping and radioIDs must be a list.")
        chosen = next((item for _, item in _wrapped(entries, ("dmr",)) if item.get("id") == settings.get("defaultID")), None)
        if chosen is None:
            chosen = next((item for _, item in _wrapped(entries, ("dmr",))), None)
        if chosen is None:
            chosen = {"id": self._next_id("id")}
            entries.append({"dmr": chosen})
        chosen.update({"name": name, "number": number})
        settings["defaultID"] = chosen["id"]

    def upsert_contact(self, number, name, contact_id=None, type="GroupCall"):
        if not _integer(number, 1, 16777215):
            raise ModelError("Contact number must be an integer from 1 to 16777215.")
        if type not in ("GroupCall", "PrivateCall", "AllCall"):
            raise ModelError("Contact type must be GroupCall, PrivateCall or AllCall.")
        table = self.data.setdefault("contacts", [])
        if not isinstance(table, list):
            raise ModelError("contacts must be a list.")
        chosen = next((item for _, item in _wrapped(table, ("dmr",)) if item.get("id") == contact_id), None)
        if contact_id and chosen is None:
            raise ModelError(f"Contact {contact_id!r} was not found.")
        if chosen is None:
            chosen = {"id": self._next_id("cont"), "ring": False}
            table.append({"dmr": chosen})
        chosen.update({"name": str(name), "number": number, "type": type})
        return chosen["id"]

    def validate(self) -> list[str]:
        """Preflight checks. qdmr's model-specific verifier remains required."""
        errors = []
        for table_name in ("radioIDs", "contacts", "groupLists", "channels", "zones", "scanLists"):
            if not isinstance(self.data.get(table_name, []), list):
                errors.append(f"{table_name} must be a list.")
        if not isinstance(self.data.get("settings", {}), dict):
            errors.append("settings must be a mapping.")
        if errors:
            return errors
        # Reject malformed IDs before any ID is used as a dictionary/set key.
        def inspect_ids(obj):
            if isinstance(obj, dict):
                if "id" in obj and (not isinstance(obj["id"], str) or not obj["id"]):
                    errors.append("Object IDs must be non-empty strings.")
                for child in obj.values():
                    inspect_ids(child)
            elif isinstance(obj, list):
                for child in obj:
                    inspect_ids(child)
        inspect_ids(self.data)
        if errors:
            return errors
        ids = set()
        def check_object(item, label):
            ident = item.get("id")
            if not isinstance(ident, str) or not ident:
                errors.append(f"{label}: missing object id.")
            elif ident in ids:
                errors.append(f"Duplicate object id: {ident}.")
            else:
                ids.add(ident)
            name = item.get("name", "")
            if not isinstance(name, str) or not name.strip() or len(name) > 16:
                errors.append(f"{label}: name must contain 1–16 characters for DM-1701.")
        radio_ids = {}
        for kind, item in _wrapped(self.data.get("radioIDs", []), ("dmr",)):
            check_object(item, "Radio ID")
            radio_ids[item.get("id")] = item
            if not _integer(item.get("number"), 1, 16777215):
                errors.append("DMR radio ID must be an integer from 1 to 16777215.")
        contacts = {}
        for entry in self.data.get("contacts", []):
            if not isinstance(entry, dict):
                errors.append("Contact must be a mapping.")
                continue
            for kind, item in entry.items():
                if not isinstance(item, dict):
                    errors.append("Contact settings must be a mapping.")
                    continue
                check_object(item, "Contact")
                if kind == "dmr":
                    contacts[item.get("id")] = item
                    if not _integer(item.get("number"), 1, 16777215):
                        errors.append("DMR contact number must be an integer from 1 to 16777215.")
                    if item.get("type") not in ("GroupCall", "PrivateCall", "AllCall"):
                        errors.append(f"Contact {item.get('id')}: invalid DMR call type.")
        groups = {}
        scans = {entry.get("id"): entry for entry in self.data.get("scanLists", []) if isinstance(entry, dict)}
        for item in self.data.get("groupLists", []):
            if not isinstance(item, dict):
                errors.append("Group list must be a mapping.")
                continue
            check_object(item, "Group list")
            groups[item.get("id")] = item
            for ref in item.get("contacts", []) if isinstance(item.get("contacts", []), list) else [None]:
                if not _contains(contacts, ref):
                    errors.append(f"Group list {item.get('id')}: unknown DMR contact {ref!r}.")
        channel_ids = set()
        has_dmr = False
        for entry in self.data.get("channels", []):
            if not isinstance(entry, dict) or len(entry) != 1:
                errors.append("Each channel must have exactly one fm or dmr mapping.")
                continue
            kind, ch = next(iter(entry.items()))
            if kind not in ("fm", "dmr", "digital", "p25"):
                errors.append(f"Unsupported channel mode {kind!r}: choose FM, DMR, or P25.")
                continue
            if not isinstance(ch, dict):
                errors.append("Channel settings must be a mapping.")
                continue
            check_object(ch, "Channel")
            ident = ch.get("id", "?")
            channel_ids.add(ident)
            for key in ("rxFrequency", "txFrequency"):
                try:
                    frequency = frequency_mhz(ch.get(key))
                    if not (Decimal(136) <= frequency <= Decimal(174) or Decimal(400) <= frequency <= Decimal(480)):
                        errors.append(f"Channel {ident}: {key} outside DM-1701 136–174 / 400–480 MHz bands.")
                    if frequency * 100000 != (frequency * 100000).to_integral_value():
                        errors.append(f"Channel {ident}: {key} must use 10 Hz precision or coarser.")
                except ModelError as exc:
                    errors.append(f"Channel {ident}: {key}: {exc}")
            if not isinstance(ch.get("rxOnly", False), bool):
                errors.append(f"Channel {ident}: rxOnly must be true or false.")
            power = ch.get("power")
            if power is not None and not isinstance(power, TaggedScalar) and power not in ("Low", "Mid", "High", "Max", "Min"):
                errors.append(f"Channel {ident}: unsupported power setting.")
            for key in ("scanList", "scanListRef"):
                if ch.get(key) is not None and not isinstance(ch.get(key), TaggedScalar) and not _contains(scans, ch[key]):
                    errors.append(f"Channel {ident}: unknown scan list {ch[key]!r}.")
            if kind == "p25":
                if not _integer(ch.get("nac", 293), 0, 0xffff):
                    errors.append(f"Channel {ident}: P25 NAC must be hexadecimal 000–FFF or FFFF for any.")
                if not _integer(ch.get("talkgroup", 1), 0, 65535):
                    errors.append(f"Channel {ident}: P25 talkgroup must be 0–65535 (0 means any).")
                if not isinstance(ch.get("audio", True), bool) or not isinstance(ch.get("promiscuous", False), bool):
                    errors.append(f"Channel {ident}: P25 audio/promiscuous must be true or false.")
                if ch.get("scanMode", "NAC + talkgroup") not in ("NAC + talkgroup", "NAC only", "No filter"):
                    errors.append(f"Channel {ident}: P25 scanMode is not recognized.")
            elif kind in ("dmr", "digital"):
                has_dmr = True
                if not _integer(ch.get("colorCode"), 0, 15):
                    errors.append(f"Channel {ident}: DMR colorCode must be an integer from 0 to 15.")
                if ch.get("timeSlot") not in ("TS1", "TS2"):
                    errors.append(f"Channel {ident}: DMR timeSlot must be TS1 or TS2.")
                if ch.get("contact") is not None and not _contains(contacts, ch.get("contact")):
                    errors.append(f"Channel {ident}: unknown DMR contact {ch.get('contact')!r}.")
                elif not ch.get("rxOnly", False) and not ch.get("contact"):
                    errors.append(f"Channel {ident}: a transmitting DMR channel needs a contact.")
                if ch.get("groupList") is not None and not _contains(groups, ch.get("groupList")):
                    errors.append(f"Channel {ident}: unknown group list {ch.get('groupList')!r}.")
            elif ch.get("bandwidth", "Narrow") not in ("Narrow", "Wide"):
                errors.append(f"Channel {ident}: FM bandwidth must be Narrow or Wide.")
        if has_dmr:
            default_id = self.data.get("settings", {}).get("defaultID")
            if not radio_ids:
                errors.append("Set your assigned DMR radio ID before programming DMR channels.")
            elif default_id is not None and not _contains(radio_ids, default_id):
                errors.append(f"settings.defaultID references unknown radio ID {default_id!r}.")
        for name, keys in (("zones", ("A", "B")), ("scanLists", ("channels",))):
            for item in self.data.get(name, []):
                if not isinstance(item, dict):
                    errors.append(f"{name} entries must be mappings.")
                    continue
                check_object(item, name)
                for key in keys:
                    refs = item.get(key, [])
                    if not isinstance(refs, list):
                        errors.append(f"{name} {item.get('id')}: {key} must be a list.")
                    else:
                        for ref in refs:
                            if isinstance(ref, TaggedScalar):
                                continue
                            if not _contains(channel_ids, ref):
                                errors.append(f"{name} {item.get('id')}: unknown channel {ref!r}.")
        return errors
