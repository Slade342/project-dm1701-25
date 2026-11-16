#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Normalize captured C6000 physical-test blocks into one dibit per byte.

This tool intentionally does not guess the radio's ordering.  The C6000
documentation defines the 36-byte block and the receive IRQ, but a live
DM-1701 measurement is still required to choose byte bit order, dibit order,
and polarity.  Run it once per candidate, then feed the resulting binary file
to the host P25 decoder.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

RAW_BYTES = 36
DIBITS = RAW_BYTES * 4


def raw_to_dibits(raw: bytes, *, lsb_first: bool, dibit_lsb_first: bool, xor: int) -> bytes:
    if len(raw) != RAW_BYTES:
        raise ValueError(f"expected {RAW_BYTES} bytes, got {len(raw)}")
    out = bytearray(DIBITS)
    for i in range(DIBITS):
        bits = []
        for bit in (2 * i, 2 * i + 1):
            byte, offset = divmod(bit, 8)
            mask = (1 << offset) if lsb_first else (0x80 >> offset)
            bits.append(1 if raw[byte] & mask else 0)
        value = (bits[0] | (bits[1] << 1)) if dibit_lsb_first else ((bits[0] << 1) | bits[1])
        out[i] = value ^ xor
    return bytes(out)


def read_records(path: Path, allow_gaps: bool):
    records = []
    expected = 0
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON: {exc.msg}") from exc
        if item.get("type") != "raw36":
            continue
        index = item.get("index")
        if not isinstance(index, int):
            raise ValueError(f"line {lineno}: raw36 record has no integer index")
        if index != expected and not allow_gaps:
            raise ValueError(f"raw36 sequence gap at line {lineno}: expected {expected}, got {index}")
        expected = index + 1
        try:
            raw = bytes.fromhex(item["hex"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"line {lineno}: raw36 hex is invalid") from exc
        if len(raw) != RAW_BYTES:
            raise ValueError(f"line {lineno}: raw36 must contain {RAW_BYTES} bytes")
        records.append(raw)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="capture JSONL from P25 lab")
    parser.add_argument("--output", type=Path, required=True, help="binary one-dibit-per-byte output")
    parser.add_argument("--lsb-first", action="store_true", help="read each raw byte least-significant bit first")
    parser.add_argument("--dibit-lsb-first", action="store_true", help="put the first raw bit in dibit bit 0")
    parser.add_argument("--xor", type=lambda value: int(value, 0), default=0,
                        help="XOR each dibit with 0..3 (use 2 for polarity reversal)")
    parser.add_argument("--allow-gaps", action="store_true", help="continue across missing raw36 indexes")
    args = parser.parse_args()
    if args.xor < 0 or args.xor > 3:
        parser.error("--xor must be 0..3")
    try:
        records = read_records(args.input, args.allow_gaps)
        dibits = b"".join(raw_to_dibits(raw, lsb_first=args.lsb_first,
                                         dibit_lsb_first=args.dibit_lsb_first,
                                         xor=args.xor) for raw in records)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(dibits)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"records": len(records), "dibits": len(dibits),
                      "lsb_first": bool(args.lsb_first),
                      "dibit_lsb_first": bool(args.dibit_lsb_first), "xor": args.xor,
                      "output": str(args.output), "radio_qualified": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
