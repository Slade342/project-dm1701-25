#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tune the experimental DM-1701 P25 receiver through its native USB link."""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
COMMAND = 0x30
PROTOCOL = "dm1701-p25/1"


def frequency_hz(value: str) -> int:
    try:
        hz = Decimal(value) * 1_000_000
        if not hz.is_finite() or hz != hz.to_integral_value():
            raise ValueError
        result = int(hz)
    except (InvalidOperation, ValueError, OverflowError):
        raise ValueError("Enter a frequency in MHz, such as 443.25000.") from None
    if not (136_000_000 <= result <= 174_000_000 or 400_000_000 <= result <= 480_000_000):
        raise ValueError("The DM-1701 receiver covers 136–174 and 400–480 MHz.")
    return result


def nac_value(value: str) -> int:
    if value.strip().casefold() == "any":
        return 0xFFFF
    try:
        result = int(value, 16)
    except ValueError:
        raise ValueError("NAC must be any or three hexadecimal digits, such as 293.") from None
    if not 0 <= result <= 0xFFF:
        raise ValueError("NAC must be between 000 and FFF.")
    return result


def decode_status(data: bytes) -> dict:
    text = data.decode("ascii", errors="replace")
    fields = {}
    for token in text.split():
        key, sep, value = token.partition("=")
        if sep:
            fields[key] = value
    if fields.get("protocol") != PROTOCOL:
        raise ValueError("This radio did not identify the Studio P25 voice protocol. Install its matching voice image first.")
    return fields


def scan_mode_value(value: str) -> int:
    """Map the CPS admission choice to the firmware command byte.

    0 keeps the selected NAC/TG policy, 1 accepts any talkgroup on the NAC,
    and 2 accepts any NAC/talkgroup.  The current firmware has no talkgroup
    admission gate, but carrying the explicit mode makes the protocol stable
    and enables the base zone scan for mode 2.
    """
    names = {"nac + talkgroup": 0, "nac only": 1, "no filter": 2,
             "normal": 0, "nac": 1, "any": 2}
    key = str(value).strip().casefold()
    if key not in names:
        raise ValueError("Scan mode must be NAC + talkgroup, NAC only, or No filter.")
    return names[key]


def configure(link, *, frequency: str | None = None, nac: str = "any",
              enable: bool | None = None, mapping: str = "auto",
              scan_mode: str | None = None) -> dict:
    current = decode_status(link.request(COMMAND, b"\x00")[1])
    if frequency is None and enable is None:
        return current
    hz = frequency_hz(frequency) if frequency is not None else int(current["rx_hz"])
    nac_int = nac_value(nac)
    try:
        mapping_int = 255 if mapping == "auto" else int(mapping)
    except ValueError:
        raise ValueError("Mapping must be auto or 0–7.") from None
    if mapping_int not in (*range(8), 255):
        raise ValueError("Mapping must be auto or 0–7.")
    enabled = enable if enable is not None else True
    # A nine-byte command remains accepted by older voice images and callers;
    # the CPS passes an explicit mode byte when using the Project DM1701-25 scan policy.
    mode_int = scan_mode_value(scan_mode) if scan_mode is not None else 0
    if mode_int == 2:
        nac_int = 0xFFFF
    payload = b"\x01" + struct.pack("<IHBB", hz, nac_int, int(enabled), mapping_int)
    if scan_mode is not None:
        payload += bytes((mode_int,))
    reply = link.request(COMMAND, payload)[1]
    # A tune is queued to the radio task, so its reply may be an acknowledgement
    # rather than the later settled state. Preserve that distinction in output.
    result = {"protocol": PROTOCOL, "request_accepted": True,
              "requested_rx_hz": hz, "requested_nac": nac,
              "requested_enabled": enabled, "requested_mapping": mapping,
              "requested_scan_mode": scan_mode or "legacy",
              "rf_reception_verified": False, "configuration_scope": "active receive profile"}
    if reply:
        result["reply"] = reply.decode("ascii", errors="replace")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="COM port, selected automatically when one radio is connected")
    parser.add_argument("--status", action="store_true", help="Read receiver status without changing it")
    parser.add_argument("--frequency", help="Receive frequency in MHz")
    parser.add_argument("--nac", default="any", help="any, or hexadecimal NAC")
    parser.add_argument("--mapping", default="auto", help="auto, or 0–7")
    parser.add_argument("--scan-mode", default="No filter",
                        help="NAC + talkgroup, NAC only, or No filter")
    parser.add_argument("--enable", choices=("yes", "no"))
    args = parser.parse_args(argv)
    if args.status and (args.frequency is not None or args.enable is not None):
        parser.error("--status cannot be combined with changes")
    try:
        if args.frequency is not None:
            frequency_hz(args.frequency)
        nac_value(args.nac)
        scan_mode_value(args.scan_mode)
        sys.path.insert(0, str(ROOT / "firmware-lab" / "vendor"))
        from rfoundry_debug import DebugLink
        with DebugLink(args.port) as link:
            result = configure(link, frequency=args.frequency, nac=args.nac,
                               enable=None if args.enable is None else args.enable == "yes", mapping=args.mapping,
                               scan_mode=args.scan_mode)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(f"P25 receiver connection failed: {exc}", file=sys.stderr)
        print("Run the Studio P25 voice firmware in normal mode, close other CPS programs, and reconnect USB. "
              "OpenGD77 and the older capture image do not implement this receiver command.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
