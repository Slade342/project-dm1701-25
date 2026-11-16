#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Guided installer for the bundled DM-1701 capture lab, NOT P25 voice firmware."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
STOCK_URL = "https://raw.githubusercontent.com/daniel5600/BAOFENG-DM1701-Original-Firmware/main/DM-1701%28CSV%29-V02.06.bin"
STOCK_SHA = "0314efd4c62625661a2d693261ae682dff8a1b075a30620f3dbda4be065de32d"


def ensure_stock(cache, opener=urllib.request.urlopen):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / "DM-1701(CSV)-V02.06.bin"
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == STOCK_SHA:
        return path
    print("Downloading the matching stock codec/key source; no file selection is needed.")
    with opener(STOCK_URL, timeout=30) as response:
        if not response.geturl().startswith("https://"):
            raise ValueError("The firmware source redirected outside HTTPS.")
        data = response.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != STOCK_SHA:
        raise ValueError("The downloaded stock source failed its pinned SHA-256 check.")
    temporary = cache / "stock.download"
    temporary.write_bytes(data)
    os.replace(temporary, path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Offline flash plan only; never opens a real radio")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "vendor"))
    from rfoundry import manifest, cli
    image = ROOT / "DM1701-CAPTURE-LAB.bin"
    meta = manifest.load(ROOT / "DM1701-CAPTURE-LAB.json")
    manifest.verify(meta, image.read_bytes(), "dm1701")
    print("DM-1701 CAPTURE LAB / experimental, not hardware-tested")
    print("This is a raw-data experiment, not working P25 voice firmware.")
    print("It replaces OpenGD77 with a RadioFoundry-based lab build.")
    print("Keep a full flash/calibration backup and a working restore route first.")
    print("Read firmware-lab/README.md before proceeding. The stock source is used for the codec/key;")
    print("the installer flashes the capture-lab image, not that stock firmware.")
    if not args.dry_run:
        if input("Type BACKED UP DM1701 to continue, or press Enter to cancel: ").strip() != "BACKED UP DM1701":
            print("Canceled; no radio was accessed.")
            return 1
    stock = ensure_stock(ROOT / ".cache")
    command = ["flash", str(image), "--board", "dm1701", "--stock", str(stock), "--codec", "merge", "--no-reporting"]
    if args.dry_run:
        command += ["--dry-run", "--no-probe", "--yes"]
    # Upstream tool keeps its model/layout/codec checks and interactive confirmations.
    # No image, key, report or calibration is uploaded to an external service.
    return cli.main(command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, NotImplementedError) as error:
        print(f"Installer stopped: {error}", file=sys.stderr)
        raise SystemExit(2)
