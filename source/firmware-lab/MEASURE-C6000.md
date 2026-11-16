# Measuring the DM-1701 C6000 symbol path

This is a receive-only diagnostic procedure. It does not make the capture-lab
image a P25 voice radio and it does not authorize transmission. The result is
useful only when a real P25 Phase 1 C4FM signal is present at the radio's tuned
frequency.

## What to record

Keep these three things together:

1. The radio capture JSONL, including its final `summary` line.
2. The exact frequency and a timestamp when a known P25 transmission was active.
3. An SDR audio/IQ recording covering the same ten-second interval, if available.

An SDR is helpful but not required. You can use a known active local P25 channel
and an online scanner or a second receiver to establish the transmission time.
If there is no known on-air signal at all, a zero-record capture cannot identify
a symbol mapping.

## Procedure on Windows

1. Make a full flash/calibration backup and retain a restore path. The capture
   image replaces the running firmware; it is not the P25 decoder image.
2. Extract the package and run `DM1701-Install.cmd` once. It creates the desktop
   shortcut and installs the bundled environment.
3. Install the capture-lab image from **Firmware → Install capture-lab firmware**
   or `Install-Capture-Lab.cmd`. If Windows reports a libusb access error, put
   the radio in its bootloader and assign WinUSB to only `0483:DF11` in Zadig.
4. Boot the lab image normally. Select an FM receive channel at the same
   frequency shown by the SDR. Turn off scanning, dual-watch, and battery-save;
   release PTT and keep the channel selected.
5. In Studio open **P25 lab → Capture radio test data**, choose a new `.jsonl`,
   and let it run for ten seconds. The capture blocks transmit in RAM and must
   be power-cycled afterward.

The capture is successful as a hardware observation when `records` is greater
than zero and `sampled_ram_changes` is nonzero. `records: 0` or an unchanged RAM
sample is still a useful failure result, but it cannot be decoded as P25.

## Trying the measured orderings

The C6000 register documentation specifies the 36-byte block but the live
DM-1701 byte/dibit order and polarity must be measured. Run:

```bat
firmware-lab\Try-C6000-Mappings.cmd first-test.jsonl
```

It tries all eight combinations of byte bit order, dibit bit order, and polarity
and writes one `.p25.jsonl` report for each. A candidate is credible only when
its NAC/sync/frame sequence agrees with the SDR recording. A host frame is not
proof that the radio can decode IMBE or drive its speaker; those still require a
board-linked, hardware-tested firmware image.

Always restart the radio after capture before returning to normal firmware.
