# DM-1701 Studio for macOS

A local FM/DMR codeplug editor and programming front end for the Baofeng DM-1701, plus a real, experimental P25 Phase 1 receive port based on Open25 Classic.

**This package does not yet make a DM-1701 receive or transmit P25.** The P25 work includes executable protocol tests and a receive-capture experiment; on-radio integration and RF testing remain unfinished. There is no P25 firmware binary to install. The established firmware route for FM/DMR is documented separately in [FIRMWARE.md](FIRMWARE.md).

## What you can use

| Component | Implemented | Remaining limit |
| --- | --- | --- |
| Mac desktop app | FM/DMR channel editing, contacts, radio ID, zones, full YAML editing | Python + Tk required; Mac launchers supplied |
| Radio programming | qdmr verification/encoding, automatic model detection, binary and YAML backup before write | qdmr installed separately; physical USB untested here |
| Stock and OpenGD77 profiles | Stock DM-1701 and OpenUV380/OpenDM1701 family | Select the actual installed firmware; USB family cannot prove the physical model |
| P25 Phase 1 workbench | Open25 framing/FEC, IMBE speech encode/decode, offline transmit assembler, independent-vector comparisons, C6000 receive probe | Needs real C6000 captures, normalization and on-board audio/RF integration |
| New radio controls/layout | C source for FPP, scanning, channel settings and an original professional-radio display | Board wiring, persistence and real tuning/transmit callbacks remain to integrate |
| Simplex repeating | Host-tested FM/P25 store-and-forward controller, bounded recording and replay/cooldown logic | Radio storage/audio/transmit paths remain to integrate; cannot listen while replaying |
| Firmware setup | Mac upstream OpenGD77 loader instructions and recovery prerequisites | Upstream downloads required; not flashed or hardware-tested here |

## Set up on your Mac

1. Extract the complete folder. Keep its contents together.
2. Install Python 3.10 or later **with Tk**. The [Python.org macOS installer](https://www.python.org/downloads/macos/) includes Tk. Alternatively, Homebrew provides `brew install python@3.13 python-tk@3.13`.
3. Double-click `Setup.command`. It creates a local `.venv` and installs PyYAML. It does not modify the radio or install firmware.
4. Double-click `DM-1701 Studio.app` or `run.command`.

The `.app` is a launcher for the included Python source, not a standalone signed binary. If Finder has removed executable permissions, run `chmod +x Setup.command run.command 'DM-1701 Studio.app/Contents/MacOS/launch'` from this folder in Terminal.

Equivalent Terminal setup:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m dm1701
```

For USB programming, install **qdmr 0.13.0 or later**; 0.15.1 is the inspected version. The author's [native Mac installation instructions](https://dm3mat.de/software/qdmr/install.html) use [MacPorts](https://www.macports.org/):

```sh
sudo port install qdmr
/opt/local/bin/dmrconf --version
```

Studio searches PATH and the normal MacPorts/Homebrew locations for `dmrconf`. You can select another executable in **Radio & backups**. `dmrconf` (qdmr) and the separate project `dmrconfig` are different tools; this app uses **dmrconf**. The editor and P25 workbench do not need an attached radio.

## Program FM and DMR

1. Select the firmware already installed on the DM-1701: **Stock** or **OpenGD77 / OpenDM1701**. Selecting a profile does not install firmware.
2. Connect the radio with its DM-1701 programming cable. In **Radio & backups**, confirm the physical model and select **Check backend**, then **Detect radio**.
3. Choose **Read & back up** before editing an existing radio. Studio retains binary `.dfu`, YAML and a manifest; the editable document is detached from its backup so Save cannot overwrite it automatically.
4. Add/edit FM or DMR channels. New channels default to receive only and are added to the first zone. Add your own assigned DMR ID when using DMR. The included example has two receive-only channels and no fabricated radio identity.
5. Use **Full codeplug** for zones, scan lists, receive groups and advanced options. Apply changes, then save your working YAML separately.
6. Select **Verify codeplug**. Stock uses qdmr's radio limit verifier. OpenGD77 uses local checks, qdmr syntax validation and model encoding: qdmr 0.15.1 crashes in its offline OpenUV380 limit verifier because its constructor dereferences a missing device. This app avoids that call. **Export binary** produces qdmr's DFU codeplug, not a manufacturer `.rdt` or firmware image.
7. **Back up & write** freezes and verifies the document, detects the firmware family, reads both backup formats, checks the backups, detects again, then programs through qdmr. Any failed prerequisite stops the write. Keep the same radio connected throughout. Afterward, read the radio and inspect its settings.

Codeplug backups are **not** full firmware, external-flash or calibration backups. See the firmware guide before replacing firmware.

Unknown YAML settings and supported qdmr tags are preserved semantically; comments and formatting are regenerated. The editor rejects duplicate keys, YAML aliases and unsupported custom tags. Local validation is deliberately conservative for the DM-1701's 136–174 / 400–480 MHz hardware ranges and 16-character labels. qdmr performs the final profile-specific checks. Enter only frequencies/settings appropriate for your operation.

## P25 development

The new code lives in [firmware-p25](firmware-p25/README.md). It reuses Open25 Classic's actual portable protocol implementation and adds a DM-1701 C6000 receive probe. It does not reuse the incompatible DM-32 register driver or image. The capture decoder accepts demodulated bits/dibits, not microphone audio, IQ or an unnormalized C6000 RAM dump.

On macOS, install Apple's command line tools if needed, then run:

```sh
xcode-select --install
cd firmware-p25
make test
./build/p25-capture --packed --nac 293 tests/protocol/vectors/clear-call.bin
make -C voice test
```

Read [P25-RESEARCH.md](P25-RESEARCH.md) for the current hardware evidence, remaining experiments and pinned source revisions. The initial port concerns conventional, unencrypted Phase 1 C4FM. No Phase 2, trunking, 700/800 MHz or P25 transmission is supplied. Adding a P25 entry to a normal DMR/FM codeplug is explicitly blocked.

## Validation and licensing

Run the Python checks with `.venv/bin/python -m unittest discover -s tests -v`. GUI tests require a display. Run the receive-core checks with `make test` inside `firmware-p25`. See `VALIDATION.md` for the actual results and their limits.

The Python application is MIT licensed. The experimental firmware subtree includes GPL-licensed Open25/OP25-derived work and separately licensed dependencies; its own notices govern that code. No manufacturer firmware or proprietary vocoder donor binary is bundled.
