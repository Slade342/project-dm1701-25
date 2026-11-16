#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental receive-only C6000 RAM capture through a RadioFoundry lab build.

Does not install firmware or transmit. Requires the documented capture-lab image,
an FM channel already tuned, and explicit acknowledgement. Output is unnormalized
raw modem RAM, NOT a decoded P25 stream. This hardware path has not been tested.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time

# The HR_C6000 physical-layer BER test is a different mode from DMR layer 2.
# The old experiment wrote a DMR sync pattern to page-1 address 0x47 (the
# oscillator-offset register in the system page), which left the modem in an
# unmeasured state and is why earlier captures showed no data-ready events.
# Keep every register touched by the documented test in the snapshot so a
# failed USB call can still be followed by a safe restart/restore attempt.
REGISTERS = (0x01, 0x07, 0x08, 0x09, 0x10, 0x40, 0x41, 0x5F, 0x81)
BER_IF = (0x0B, 0xD9, 0x54)  # documented 455-kHz physical-test IF


def capture(link, seconds, emit, now=time.monotonic, idle=time.sleep):
    if not 0 < seconds <= 30:
        raise ValueError("Capture duration must be between 0 and 30 seconds.")
    version = link.version()
    if "DM-1701" not in str(version.get("board", "")):
        raise ValueError("This capture experiment requires the DM-1701 lab firmware.")
    core = link.view(["core"])
    if core.get("mode") != "fm" or core.get("state") not in ("rx", "idle", "tx_denied"):
        raise ValueError("Select an FM receive channel and release PTT before capture.")
    link.probe_status()  # Refuses a normal firmware build without AUDIO_PROBE.
    link.tx_limit(block=True)  # RAM-only inhibit: power cycling clears it.
    if link.view(["core"]).get("txlim") != "block":
        raise ValueError("The radio did not confirm that transmitting is blocked.")
    saved = {r: link.probe_reg(4, r) for r in REGISTERS}
    emit({"type": "header", "version": version, "radio": core, "hardware_qualified": False,
          "data_format": "C6000 physical-test raw36 RAM; packed bits, symbol ordering unmeasured",
          "mode": "physical-ber-continuous", "tx_block": True})
    records = 0
    polls = 0
    flags_seen = {}
    ram_changes = 0
    previous_ram = None
    last_status = core
    error = None
    restored = True
    try:
        # HRC6000-registers.md 6.4 / table 5.6: IF receive, continuous
        # physical-layer mode, RX test enabled.  The test owns no TX path.
        hw_config = saved.get(0x01, 0) & 0xF0
        for r, value in ((0x40, 0), (0x41, 0), (0x81, 0),
                         (0x01, hw_config), (0x07, BER_IF[0]),
                         (0x08, BER_IF[1]), (0x09, BER_IF[2]), (0x10, 0x02)):
            link.probe_reg(4, r, value)
        for r, value in ((0x5F, 0x00), (0x83, 0xFF), (0x81, 0x01),
                         (0x40, 0x40), (0x41, 0x41)):
            link.probe_reg(4, r, value)
        emit({"type": "registers", "stage": "configured",
              "system": {f"0x{r:02x}": link.probe_reg(4, r) for r in REGISTERS},
              "physical_test": {"if_hz_nominal": 455000, "rx_ram": "page2:0x030",
                                 "irq_bit": 0, "raw_bytes": 36}})
        started = now()
        check_at = started
        while now() - started < seconds:
            current = now()
            if current >= check_at:
                state = link.view(["core"])
                last_status = state
                # Diagnostic samples are not packets: no data-ready indication
                # is required, and they must never be treated as decoded P25.
                sample = bytes(link.probe_ram(2, 0x30, n=36))
                if previous_ram is not None and sample != previous_ram:
                    ram_changes += 1
                previous_ram = sample
                emit({"type": "ram_sample", "host_us": int((current-started)*1000000),
                      "hex": sample.hex(), "rssi_dbm": state.get("rssi_dbm"),
                      "state": state.get("state"), "not_a_validated_packet": True})
                if state.get("mode") != "fm" or state.get("rx_hz") != core.get("rx_hz") or state.get("txlim") != "block" or state.get("state") == "tx":
                    raise RuntimeError("Radio channel/mode/receive ownership changed during capture.")
                check_at = current + 0.5
            flags = link.probe_reg(4, 0x82)
            polls += 1
            flags_seen[str(flags)] = flags_seen.get(str(flags), 0) + 1
            if flags & 1:
                kind = link.probe_reg(4, 0x51)
                ram = bytes(link.probe_ram(2, 0x30, n=36))
                if len(ram) != 36:
                    raise RuntimeError("Incomplete C6000 RAM reply.")
                # The chip's documented clear operation is write-back of the
                # complete flags byte, not just bit 0.  In this mode bit 0 is
                # the physical-layer receive indication.
                link.probe_reg(4, 0x83, flags)
                emit({"type": "raw36", "index": records, "host_us": int((now()-started)*1000000),
                      "irq": flags, "kind": kind & 3, "hex": ram.hex()})
                records += 1
            else:
                idle(0.001)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        # Attempt every restoration even if one fails. Never restore TX enables.
        values = [(4, 0x40, 0), (4, 0x41, 0), (4, 0x81, 0)]
        values += [(4, r, value & 0x7F if r in (0x40, 0x41) else value) for r, value in saved.items()]
        for page, register, value in values:
            try:
                link.probe_reg(page, register, value)
            except Exception:
                restored = False
        emit({"type": "summary", "records": records, "error": error, "register_restore": restored,
              "tx_block_remains_until_restart": True, "missing_or_reordered_blocks": "unmeasured",
              "polls": polls, "irq_histogram": flags_seen, "sampled_ram_changes": ram_changes,
              "last_radio_status": last_status})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="USB serial port; automatically selects the single connected lab radio")
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--acknowledge-experimental", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_experimental:
        parser.error("Read README.md, then pass --acknowledge-experimental for this receive-only experiment.")
    if not 0 < args.seconds <= 30:
        parser.error("--seconds must be greater than 0 and at most 30")
    sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
    from rfoundry_debug import DebugLink
    # Exclusive creation keeps earlier experiment data intact.
    with args.output.open("x", encoding="utf-8") as out:
        def emit(record):
            out.write(json.dumps(record) + "\n")
            out.flush()
        with DebugLink(args.port) as link:
            count = capture(link, args.seconds, emit)
    print(f"Saved {count} data-ready records plus modem diagnostics. Zero records is inconclusive, not a P25 pass. Power-cycle the radio after the experiment.")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
