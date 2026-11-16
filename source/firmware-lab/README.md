# DM-1701 capture lab — Windows first

This folder contains an actual, complete STM32 DM-1701 firmware image, its ELF
and manifest, a guided installer, and a new receive-data capture tool.

**It does not provide P25 voice reception or transmission.** It is a RadioFoundry
build with `CONFIG_AUDIO_PROBE=y`, used to test access to the C6000 modem's raw
receive buffers. The Open25 decoder, speech codec, new UI/FPP/scan/simplex source
in `firmware-p25` is not linked into this image. A successful compile and checked
memory layout do not establish that this image boots or receives on your radio.
Physical testing remains outstanding.

## What has been checked

| Item | Result |
| --- | --- |
| Target | Baofeng DM-1701, STM32F405, app base `0x0800C000` |
| Base source | RadioFoundry `947c1398fe85f2c0314f7749888e627270b23679` |
| Configuration | Default DM-1701 features plus `CONFIG_AUDIO_PROBE=y` |
| Image size | 535924 bytes |
| Image SHA-256 | `1756b75934f977c114988f4f0b07961aa7185c6acf889cc8a02771c190515bc5` |
| Stack pointer | `0x2001FFFC`, inside the board's SRAM |
| Reset vector | `0x080744A1`, Thumb entry inside application flash |
| Flash use | 535924 / 737280 bytes; no bootloader or codec-sector overlap |
| SRAM / CCM use | 117600 / 131068 bytes; 64872 / 65536 bytes |
| Hardware boot / RX / TX | Untested |

`build-report.json` and `DM1701-CAPTURE-LAB.json` retain these checks. The small
remaining CCM budget matters: integrating the IMBE codec will require deliberate
memory budgeting and likely disabling unused features.

## Before installation

Make and retain your own full OpenGD77 external-flash and calibration backup,
your working codeplug, and the files/tools needed to restore your current radio.
Studio's channel/codeplug backup is **not** a full flash/calibration backup.
See `../FIRMWARE.md` for the backup distinction and recovery references. This
installer replaces OpenGD77 with a RadioFoundry lab build; it does not add a mode
to OpenGD77. Do not install this first experiment on a radio you depend on.

The bundled image is raw ARM firmware. Do not feed it to the manufacturer CPS or
the OpenGD77 donor loader: the matching RadioFoundry tool must process its
manifest, codec and bootloader encoding.

## Guided installation on Windows

1. Run `Setup-Windows.cmd` in the package root once.
2. Close other radio/CPS programs. Detach the radio from WSL USB forwarding if
   using it for qdmr (`usbipd detach --busid YOUR-BUS-ID`). Firmware loading and
   capture use native Windows USB/serial access.
3. Read this guide and complete the backups above.
4. In Studio choose **Firmware → Install capture-lab firmware**, or run
   `Install-Capture-Lab.cmd` from the package root.
5. The installer opens a console and asks you to acknowledge the backups. It
   checks the bundled image, downloads the exact stock DM-1701 V02.06 codec/key
   source automatically, verifies its pinned SHA-256, and calls the bundled
   upstream `rfoundry` flasher. No file browsing is needed.
6. Follow the tool's radio/model checks and confirmations. To enter the DM-1701
   bootloader, power off, hold **PTT + the small side button above PTT**, and turn
   on. The display stays dark and the indicator flashes red/green. Keep a charged
   battery and the USB cable connected until the tool finishes.

Native USB flashing on Windows requires a compatible WinUSB/libusb driver for
the **bootloader's** USB interface. The libusb runtime is included as a Python
dependency; it does not install a Windows kernel driver. If the tool reports a
driver/access error, follow the matching RadioFoundry upstream Windows USB
instructions and check the device in Device Manager before retrying. A driver
change can affect the original CPS, so retain its driver/restore instructions.

If the error ends in `NotImplementedError: Operation not supported`, Windows
enumerated the device but its current driver does not support libusb access.
With the radio in bootloader mode, use Zadig from https://zadig.akeo.ie:
Options → List All Devices, select **Digital Radio in USB mode** with USB ID
**0483:DF11**, then choose **WinUSB** and Install/Replace Driver. Confirm the
device disappears from Zadig's list when that radio is unplugged before changing
its driver; do not select an unrelated USB device. Close other CPS/USB programs,
reconnect in bootloader mode, and rerun the installer. This change may require
restoring the former driver to use the original manufacturer CPS later.

The stock source is downloaded on your computer from the public archive linked
by RadioFoundry, used for the matching codec and bootloader key, and kept in
`.cache`. It is not included in this package or installed as the radio firmware.
The flasher's external reporting is disabled. Calibration and backups are not
uploaded. The actual Windows driver, DFU and first-boot flow remains untested here.

## First receive-data experiment

Use a known P25 Phase 1 **C4FM** signal within 136–174 or 400–480 MHz. An SDR can
help confirm the signal/frequency. An ordinary receive-only SDR cannot generate
the test signal; a known transmitter or suitable existing signal is still needed.
This experiment does not cover Phase 2, LSM/CQPSK or 700/800 MHz.

1. Start the lab firmware normally and select an **FM receive channel** at the
   intended frequency. The host then puts the modem into experimental physical
   receive mode. Turn scanning, dual watch and receiver battery saving off.
2. Keep the same channel selected during the capture. Close other USB clients.
3. In Studio open **P25 lab → Capture radio test data**. Choose a new `.jsonl`
   output file. The script automatically selects the single lab radio COM port.
4. It checks the reported board and FM state, sets a RAM-only transmit block,
   saves registers, writes the documented C6000 physical-layer BER experiment
   (including its 455-kHz test IF), and polls 36-byte raw receive blocks for
   ten seconds.
5. It attempts to restore the saved receive registers. **Restart the radio after
   every experiment**; the transmit block deliberately remains until restart.
6. Share the resulting `.jsonl` file, test frequency and SDR recording if you have
   one. Report whether the radio booted, whether records were captured, and any
   console error. A zero-record result is useful evidence too.

Equivalent Windows command:

```bat
.venv\Scripts\python.exe firmware-lab\capture.py --seconds 10 --output first-test.jsonl --acknowledge-experimental
```

Use `--port COM7` if automatic serial selection is ambiguous. The output is
unnormalized physical-test modem RAM, **not** a P25 bitstream, IQ recording or
decoded voice. The new ARM adapter can try measured byte/dibit/polarity mappings
after a live capture; it does not guess a mapping from this file.
Host timestamps and counters cannot prove that no modem blocks were dropped.
We must establish RAM field order, bit order, continuity and filtering using
real results before feeding normalized data into the supplied P25 decoder.
This script does not transmit, alter calibration or install firmware.

After a capture, normalize one candidate ordering for the host decoder (the
defaults are only a documented starting point, not a qualification):

```bat
Normalize-C6000-Capture.cmd first-test.jsonl first-test.dibits --xor 0
```

The output is one binary dibit (0--3) per symbol. Try the other explicit
ordering controls (`--lsb-first`, `--dibit-lsb-first`, `--xor 2`) only while
comparing against the SDR reference; a candidate that produces JSON P25 frames
is still subject to NAC/FEC and audio validation.

With the bundled Windows host decoder, `Decode-C6000-Capture.cmd` performs both
steps and writes `<capture>.p25.jsonl`. A no-frame result is useful evidence; it
does not mean the radio's speaker path is working or that an RF mapping has
been qualified.

## Rebuild / provenance

The image uses the unchanged upstream RadioFoundry source and pinned submodules:

```sh
git clone https://github.com/RadioFoundry/RadioFoundry.git
cd RadioFoundry
git checkout 947c1398fe85f2c0314f7749888e627270b23679
git submodule update --init
make BOARD=dm1701 CONFIG_AUDIO_PROBE=y BUILD=build/dm1701-capture-lab
```

An Arm GNU toolchain with newlib is required; this build used GCC 14.2.1 and
newlib 4.5.0. `vendor/rfoundry` and `vendor/rfoundry_debug.py` come from that same
commit. Their MIT notices and AUTHORS are retained. The source and runtime
licenses are under `LICENSES`; the capture/installer integration is GPL-3.0-or-later.
The separately downloaded stock donor is proprietary upstream material and is
not redistributed here.
