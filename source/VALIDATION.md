# Validation record — Studio 0.3

The 0.3 release includes a complete linked P25 receive application. These checks
ran on Linux; no physical DM-1701 or Windows execution was available.

| 0.3 check | Result |
| --- | --- |
| Desktop model/backend/native-link/GUI suite | 81 tests passed using the actual Tk application on an Xorg display |
| Exact receiver integration with real IMBE codec | Eight candidate raw36 orderings each recovered 32 P25 frames and 261 PCM blocks from reference speech; stale-generation rejection and failed-start rollback passed |
| ARM application | Linked with Arm GNU 14.2.1 at `0x0800C000`; P25 polling, FEC, IMBE, speaker callback and home renderer present; no undefined symbols |
| Radio display | Actual renderer ran on a 160×120 indexed panel / 150×120 safe-area host buffer; `firmware-voice/radio-home.png` is its output |
| Installer preflight | Matching manifest/hash/vector/sector checks and offline donor/codec flash plan passed; bootloader excluded from the plan |
| Windows setup | NSIS package bundles pinned Python 3.12 x64 and offline dependencies; Windows installation/USB execution unverified |

The final image's exact hash, bytes and configuration are in
`firmware-voice/build-report.json` and its release manifest. RF raw-block timing,
real-time ARM decode speed, first boot, actual speaker output and interoperability
remain unverified. P25 is conventional clear Phase 1 C4FM RX only; no trunk
following, Phase 2, encryption or P25 TX is included.

The older capture image and relocatable-component results below are historical;
their statements about features not linked apply to those older artifacts.

## Earlier workbench and capture checks

Checked November 15, 2026. All executable checks here ran on Linux; Windows, macOS and a physical DM-1701 were unavailable. Windows execution, drivers, DFU flashing and hardware boot are unverified. Mac launchers and upstream loader routes were inspected, not executed on a Mac. The extracted release archive passed its integrity checks; the Python suite contains 72 tests and requires its optional GUI/USB dependencies for a complete run.

| Check | Actual result |
| --- | --- |
| Python model, backend, native USB discovery, image integrity, capture transactions and real Tk user flows | 64 unittest tests passed with an Xorg dummy display |
| Real qdmr 0.15.1 stock profile | Example with explicit test radio ID passed verification and binary encoding |
| Real qdmr 0.15.1 OpenUV380 profile | Syntax validation and actual binary encoding passed |
| OpenUV380 offline limit verification | Upstream crash reproduced; the app avoids it using syntax/local/encode checks |
| Portable P25 protocol | All 20,480 NAC/voice-DUID combinations matched pinned OP25 reference; 1,000 damaged NIDs and 250 packet vectors passed |
| P25 stream/capture | Inversion, NAC filtering, frame reacquisition, damaged metadata, lengths and packed/dibit inputs passed |
| Experimental C6000 receive probe | Default gate, ownership, receive-only register writes, restoration, IRQ acknowledgement, gaps, overflow and bus-failure tests passed with a fake HAL |
| Documented C6000 physical BER setup | Probe/capture now uses `0x01=xxxx0000`, IF `0x0BD954`, `0x10=0x02`, `0x40=0x40`, `0x41=0x41`, raw RAM `2:0x030`, and write-back IRQ clearing; host transaction tests passed |
| RadioFoundry register bridge | Compiled against the pinned public header; page/address limits and TX rejection passed |
| Cortex-M4 compilation | Protocol, disabled/enabled receive probe and bridge compiled to ARM ELF objects with clang 22.1.8; no board link or firmware image |
| ARM P25 audio component | `make arm-p25` produced a 35,261-byte Cortex-M4 relocatable object with C6000 raw36 adapter, fixed-point IMBE decoder, and bounded speaker FIFO; unresolved-symbol check passed |
| New FPP and scanning engine | Transactional save/cancel, invalid settings, persistence failure, scan membership/hold/resume, timer rollover, PTT and failed tuning passed |
| Simplex controller | FM/P25 recording/replay, clear-traffic gating, bounds, busy-channel timeout, cooldown, rollover and storage failure passed |
| Speech TX/RX workbench | Generated 440 Hz audio -> 18 IMBE frames -> P25 call frames -> receive/FEC -> PCM passed; length, nonzero audio and malformed input checked |
| Windows host capture decoder | Cross-compiled `firmware-p25/windows/p25-capture.exe` is PE32+ x64; execution on Windows remains untested |
| Complete capture-lab image | RadioFoundry DM-1701 with AUDIO_PROBE compiled/linked using Arm GNU 14.2.1; vectors, model manifest, hash and memory ranges checked |
| Guided installer preflight | Actual pinned stock source passed hash, bootloader-key derivation and codec-window checks; offline erase/write plan succeeded without USB access |

The voice test is a host round trip. It does not measure intelligibility, real-time ARM performance, RF sensitivity, transmit deviation, spectral purity, or interoperability. The UI/FPP/scan/simplex code is not integrated into a running DM-1701 image. No P25 over-the-air RX or TX claim is made.

The qdmr OpenUV380 problem has a concrete source cause in v0.15.1: `cli/verify.cc` instantiates `OpenUV380` without a device; `lib/openuv380.cc` dereferences `device->extendedCallsignDB()` in its constructor. The app's OpenGD77 preflight uses qdmr YAML syntax checks, local DM-1701 checks and actual model-specific encoding instead of that crash-prone call. This does not supply qdmr's complete offline limit verification. Both USB programming profiles remain physically untested.

No radio or RF transmitter was operated. The firmware loader was exercised only in offline plan mode with USB probing disabled. A real capture-lab image is now included; its boot and RF behavior remain untested. The workbench bitstreams are synthetic tests, separate from that lab firmware. Test radio IDs were confined to temporary local verification files and are not supplied as your identity.

Reproduce:

```sh
python3 -m unittest discover -s tests -v
make -C firmware-p25 test
make -C firmware-p25/voice test
```

GUI cases skip without a display. Cortex-M4 checks require Arm GNU, clang with an ARM target, or Zig; see `firmware-p25/tools/arm_check.py`. JSON reports under `firmware-p25/validation` record the actual protocol and ARM compilation results.
