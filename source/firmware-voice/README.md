# Project DM1701-25 experimental P25 voice application

`PROJECT-DM1701-25-P25-EXPERIMENTAL.bin` is a complete STM32F405 application linked at
`0x0800C000`. Its matching `.json` contains size/SHA-256; `build-report.json`
records components and build command. `.elf` and `.map` retain debug symbols.

It links live C6000 raw-block polling, eight candidate symbol mappings, P25
framing/BCH/Golay/Hamming/RS recovery, software IMBE voice decoding, a 16×160 PCM
queue, and the board's I2S speaker callback. The new home screen is an original
professional-radio layout sized for the DM-1701 display.

**Boot, RF reception and speaker audio are unverified on a physical radio.**
The modem's raw output may still prevent frame recovery. It attempts clear
conventional Phase 1 C4FM RX only. No P25 transmitter, affiliation, trunk following,
Phase 2 or encryption is implemented. Control channels do not carry speech.

Use **Firmware installation → Install Project DM1701-25 P25 firmware** in Project DM1701-25. The source
installation alternative is `Install-P25-Voice.cmd`. The installer verifies the
image and downloads a pinned donor for its matching bootloader key/DMR codec.
It retains upstream board/layout checks, protects the bootloader, and disables
external reporting. Keep a full flash/calibration backup and restore tools.

After flashing, reboot normally. In **P25 receiver**, enter MHz and NAC (`any`
or hex), choose `No filter` when you want every clear conventional call, then
**Start receiving**. Read P25 receiver shows actual counters/errors.
The active profile persists after a settings save (about two seconds) or normal
power-off. The complete channel list stays in your local CPS project.

Hold **#** on an FM Home channel to toggle P25. Use VFO/channel editing for front-
panel frequency changes. Names beginning with `P25` request P25 reception. A
no-filter request also asks the configured zone scan to walk receive-only P25
channels.
P25 blocks PTT; FM/DMR retain their base-firmware behavior.

```bat
.venv\Scripts\python.exe firmware-voice\radio.py --status
.venv\Scripts\python.exe firmware-voice\radio.py --frequency 443.25000 --nac any --enable yes
```

`firmware-p25/integration/build_voice_image.py` recreates the derivative from
pinned RadioFoundry with its submodules. The accompanying source archive contains
the derivative including upstream notices. MIT source files retain their licenses;
the combined P25 work is GPL-3.0-or-later. The About page retains RadioFoundry's
copyright. No donor firmware is in the source archive.
