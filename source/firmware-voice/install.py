#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the matching complete experimental DM-1701 P25 receiver image."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "firmware-lab"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Verify image and print flash plan; no radio access")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(LAB / "vendor"))
    from rfoundry import manifest, cli
    image = ROOT / "PROJECT-DM1701-25-P25-EXPERIMENTAL.bin"
    if not image.is_file():
        # Keep old Studio copies recoverable while all new installers use the
        # Project DM1701-25 image name.
        image = ROOT / "DM1701-P25-VOICE-EXPERIMENTAL.bin"
    meta_path = image.with_suffix(".json")
    if not image.is_file() or not meta_path.is_file():
        raise ValueError("The complete voice image and manifest are missing. No radio was accessed.")
    meta = manifest.load(meta_path)
    manifest.verify(meta, image.read_bytes(), "dm1701")
    print("Project DM1701-25 0.4 — experimental P25 Phase 1 receive firmware", flush=True)
    print("Includes the software speech decoder and speaker integration; over-air reception has not been verified.", flush=True)
    print("Replaces the current application. Keep a full flash/calibration backup and working restore files.", flush=True)
    if not args.dry_run:
        if input("Type INSTALL P25 to continue, or press Enter to cancel: ").strip() != "INSTALL P25":
            print("Canceled. No radio was accessed.")
            return 1
    spec = importlib.util.spec_from_file_location("studio_lab_installer", LAB / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    stock = module.ensure_stock(LAB / ".cache")
    command = ["flash", str(image), "--board", "dm1701", "--stock", str(stock),
               "--codec", "merge", "--no-reporting"]
    if args.dry_run:
        command += ["--dry-run", "--no-probe", "--yes"]
    return cli.main(command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Voice firmware installer stopped: {error}", file=sys.stderr)
        raise SystemExit(2)
