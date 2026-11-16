# Source and license provenance

This research subproject is GPL-3.0-or-later. Preserve the full license in
`LICENSE` and upstream notices when redistributing it. It is separate from the
programming app; no proprietary codec, firmware image, calibration or dump is
included.

The unchanged portable protocol implementation in `vendor/open25/` comes from:

- https://github.com/tylerwatt12/Open25-DM32
- commit `19420686920fdd37a6554285d0aa5f5d5ce8a36f`
- original files: `src/p25/p25.c`, `p25.h`, `p25_runtime.h`,
  `golay_table.inc`, `generate_tables.py` (GPL-3.0-or-later).
- `tests/test_protocol.py` adapts that commit's `tests/protocol/test_p25.py`.
  It retains the independent BCH/full-frame oracle, stream and metadata damage
  tests; it omits tests requiring the complete OP25 C++ helper dependency.

The independent reference `vendor/op25/p25craft.py` comes from:

- https://github.com/boatbod/op25
- commit `3f44d43eb449bb4753247ce848bb42a403823dea`
- original file `op25/gr-op25_repeater/apps/tx/p25craft.py`.
- Copyright 2011 Michael Ossmann; GPL-2.0-or-later, combined here under GPL 3.
- SHA-256 `27079a321f75bda5db8d3ef6dd30d65992dbf8b6c73a2c608b43f3f745e9e2d9`.

The new C6000 receive probe was written against published register facts in:

- https://github.com/RadioFoundry/RadioFoundry
- commit `947c1398fe85f2c0314f7749888e627270b23679`
- `docs/spec/hrc6000-registers.md`, sections 2.2 (raw receive RAM),
  3.18 (interrupt registers), 4.1 (sync patterns), 6.4 (continuous PHY BER test).
- `docs/spec/modem-hrc6000.md`, section 9.2 (bench-confirmed raw transmit
  operation, evidence for physical-layer access, not a P25 qualification).
- `docs/spec/hardware-dm1701.md` (board RF, IF, PCM and MCU constraints).

The experiment uses the documented continuous PHY BER receive settings
`0x01=xxxx0000`, `0x07..0x09=0x0BD954` (455 kHz), `0x10=0x02`,
`0x40=0x40`, `0x41=0x41`, RX IRQ `0x82 bit 0`, write-back acknowledgement
`0x83`, and raw RX RAM page 2 offset `0x30`. It does not write a page-1 sync
comparator; the physical test reports each 36-byte demodulated block directly.
These are documented register meanings; their combined operation on live P25 in
a DM-1701 has not been measured. The probe snapshots and restores the touched
IF/system registers and always leaves TX disabled while it owns the experiment.

The probe includes no RadioFoundry implementation code. Integration must supply
board HAL callbacks and own/exclude the normal modem ISR. Its GPL terms also
apply to a firmware derivative that incorporates it. Open25 Classic's C7000
register driver, C-SKY binary and its flashing packages cannot be used on a
C6000/STM32 DM-1701 unchanged.

`src/radiofoundry_bridge.*` adapts its pinned public `hrc_read_burst` and
`hrc_write_burst` interface. The unmodified public header in
`vendor/radiofoundry/modem/hrc_common/hrc.h`, MIT license and AUTHORS file are
retained. The new adapter is GPL-3.0-or-later; this is an external derivative,
not a contribution of GPL code to RadioFoundry's clean-room MIT repository.

`voice/vendor/` contains nostar/imbe_vocoder at commit
`03423cb00b8e9ba1be164493e8b98b5bd7c1508c`, matching Open25's source lock.
Pavel Yazev's GPL-3.0-or-later notices are retained. Original front-panel,
scanning, display, transmit-file and voice-workbench integration code in this
subproject is also GPL-3.0-or-later. The original RadioFoundry authors' names
and license are preserved; no upstream copyright notice has been replaced.
