# DM-1701 P25 research port

This includes a working **P25 Phase 1 conventional protocol/capture decoder**, real
**IMBE audio encoder/decoder**, offline **transmit-frame assembler**, portable
**FPP/scan/display engine**, and an **experimental C6000 receive-capture component**. It is not a flashable firmware
image and does not yet make a DM-1701 receive or transmit P25 over RF.

The user asked for a genuine attempt at the Open25 approach. Open25 Classic's
portable CAI framing/FEC code is usable on this radio's Cortex-M4. Its DM-32
C7000 register/IRQ driver is not: the DM-1701 uses a separate C6000 modem and
STM32 host. C6000 documentation exposes a continuous physical-layer BER test
and raw 36-byte blocks, which gives a concrete experiment to pursue rather than
assuming that P25 is impossible. The raw-block-to-dibit adapter and fixed-point
IMBE/speaker path now cross-compile for Cortex-M4, but the live byte/bit
permutation and board link still need measurement on a real DM-1701.

## Run on macOS

Install Apple's Command Line Tools if `cc` and `make` are unavailable:

```sh
xcode-select --install
```

With Python 3 installed, in this directory:

```sh
make
make test
./build/p25-capture --packed --nac 293 tests/protocol/vectors/clear-call.bin
```

The test creates the sample vector from an independent, pinned OP25 reference.
The decoder prints four JSON lines: HDU, LDU1, LDU2 and terminator, NAC `293`,
talkgroup 123 and source ID 123456 where those fields exist. The sample contains
synthetic IMBE parameter vectors, not recorded speech.

To inspect your own already-demodulated conventional P25 captures:

```sh
./build/p25-capture --packed --nac any capture.bin
./build/p25-capture --dibits --nac 293 capture.dibits
```

Packed input is MSB-first on-air bits including status symbols. Dibit input is
one binary byte per symbol, value 0..3. Input is **not** WAV, IQ, discriminator
audio or a C6000 raw RAM dump. Modem RAM may reorder bits; it must first be
measured and normalized. The CLI synthesizes no speech; it decodes the packet
metadata/FEC and identifies the nine channel-coded IMBE frames in each LDU.
The capture CLI itself emits metadata. The separate [voice workbench](voice/README.md)
decodes/encodes speech and exercises audio through the transmit/receive protocol path.
No trunking, Phase 2 or encryption implementation is included.

## What is implemented and checked

- Open25's portable conventional Phase 1 BCH NID, Golay/Hamming/RS FEC,
  HDU/LDU1/LDU2/TDU/TDULC framing, IMBE channel coding and stream recovery.
- Independent OP25 oracle comparison for all 20,480 NAC/voice-DUID pairs,
  1,000 damaged NIDs with up to 11 errors, and 250 full packet vectors.
- Inverted symbols, NAC filtering, lost-frame reacquisition, bad sync/lengths,
  metadata correction and the encrypted-audio indication.
- A new receive-only C6000 raw-capture component with explicit ownership,
  snapshots/restoration, bounded ISR ring, sequence numbers, gap detection via
  the consumer, and bus-fault shutdown. Its fake-HAL tests check every write for
  forbidden TX bits. They do not qualify a real radio.
- Real IMBE PCM encoding and decoding, with a generated-audio call passed through
  P25 framing/FEC and back to PCM (`make -C voice test`).
- A bounded ARM-side P25 audio pipeline (`src/p25_audio_pipeline.c`) that accepts
  normalized C4FM dibits, performs NID/FEC/frame recovery, calls a board-supplied
  IMBE decoder, and writes 160-sample frames to a board-supplied speaker callback.
  It uses no heap allocation and is covered by a host stream/audio pacing test.
- `src/dm1701_c6000_adapter.c` converts the documented 36-byte physical-test
  block into 144 dibits with explicit byte order, dibit order, and polarity
  controls. `src/p25_speaker_fifo.c` provides a bounded single-producer,
  single-consumer 8-kHz PCM queue for the board's I2S/audio task.
- `make arm-p25` cross-compiles the fixed-point IMBE decoder and combines it with
  the protocol, C6000 adapter, and speaker FIFO into a **35,261-byte** Cortex-M4
  relocatable component (report: `build/arm/p25-audio-report.json`). The
  component is deliberately not a flash image: it still needs the live radio's
  measured raw-block mapping, C6000/ISR ownership, board linker/startup, and
  I2S callback integration.
- An offline transmit assembler, `build/p25-txfile`, that takes BE16 IMBE vectors
  and emits HDU, alternating LDU1/LDU2 and TDU. It has no radio/RF access.
- Transactional FPP, a 64-channel store, configurable receive/transmit frequencies,
  mode, NAC, talkgroup, unit ID, DMR settings, scan membership and RX-only control.
- Scan dwell, traffic hold and resume with wrap-safe millisecond timers; a failed
  tune prevents PTT. Board callbacks must provide actual tuning and persistence.
- An original professional-radio layout for the visible 160x120 DM-1701 panel.
  `build/radio-layout > radio-layout.svg` renders the same C display function.
- An FM/P25 **store-and-forward simplex repeater controller** with a 20-second
  recording limit, end-of-call detection, bounded storage, playback timeout,
  two-second cooldown, same-frequency validation and fault shutdown. It needs
  board recording/storage/playback callbacks and is disabled initially.

## Simplex repeat

`src/simplex.h` provides the tested controller. It receives a call, waits for
500 ms of channel silence, then replays the stored call on the same frequency.
It cannot receive during replay. New activity resets a two-second cooldown after
replay, helping to prevent repeated self-triggering. It gives up instead of
replaying over an occupied channel. Recording is bounded to 20 seconds and
128000 bytes by default; the board can set lower limits to suit its actual
storage allocation. Do not point it at an existing calibration/codeplug area.

FM needs real squelch-qualified audio capture and an audio replay path, optionally
using ADPCM for storage. P25 needs normalized, valid **clear** IMBE frames and
their NAC/talkgroup/call metadata, followed by fresh P25 framing for playback.
The controller never records encrypted P25 traffic and has no decryption code.
The board must implement its storage and real RF transmit callbacks before it
does anything on the radio. Host tests use simulated storage/audio; they cover
call endings, busy-channel handling, recording limits, rollover, errors and
cooldown. This is not yet an operational simplex repeater firmware.

## FPP, scanning and board integration

`src/radio_app.h` documents the board callback and display interfaces. `radio_key`
handles menu, next/up/down, save/cancel, scan and PTT. `radio_digit` supplies keypad
characters to the selected FPP field. RX/TX frequencies use MHz with up to 10 Hz
precision; NAC is hexadecimal. The board must map its physical keys (including
decimal/hex/name entry), write an atomic settings record, tune RF/modem modes,
and call `radio_tick` with **decoded matching activity**, not raw RSSI.

The engine's `tx_begin` callback deliberately has no default implementation. It
must report success only after a real, qualified P25 modem/audio transmitter is
ready. A PC test callback is not that implementation. Its implementation and
rendering are source for the new firmware; they have not been installed on the
radio. The normal-home view currently has one zone and a 64-channel store; full
zone management, text-entry ergonomics and scan-priority features remain future work.

`make arm-check` cross-compiles the protocol and probe to Cortex-M4 ARM objects
using Arm GNU or LLVM clang, or run
`python3 tools/arm_check.py --zig /path/to/zig`. This checks portable target
compilation; it does not link a board image or establish timing/interop.

## Actual hardware experiment still required

`src/dm1701_rx_probe.c` is compiled with hardware access disabled by default.
An experienced firmware developer must integrate it with the DM-1701 board's
C6000 SPI and ISR ownership and implement `rx_safe()` so PTT stays locked, the
PA stays disabled and RF routing stays on receive. Build it separately with
`DM1701_EXPERIMENTAL_RX=1` only for that instrumented experiment. The API also
requires an explicit acknowledgement of the unverified path. No flasher or
firmware image is provided.

The probe uses the documented C6000 BER-test physical RX mode. It snapshots and
restores the touched system registers, temporarily selects the manual's 455-kHz
physical-test IF, never writes a TX enable or page-1 sync address, and marks every
copied block with a sequence number. Saved TX enables are deliberately cleared
during restoration; the normal board owner must resume ordinary receive after
ending the experiment.
The board HAL remains responsible for immediate hardware RF safety on bus errors.
Callbacks used by the ISR must themselves be ISR-safe and bounded.

Acceptance measurements before claiming DM-1701 P25 reception:

1. Known C4FM source at a supported VHF/UHF frequency: compare every 36-byte
   completion against an SDR reference, establish the actual field permutation
   and byte/bit order, and verify 4,800 continuous symbols/s without dropped or
   duplicated data across calls and silence. Documentation's DMR-shaped raw
   buffer layout must not be assumed to be unmodified on-air order.
2. Measure sync acquisition, IRQ period and buffer overwrite deadline; establish
   error handling and restore normal DMR/FM after capture.
3. Feed normalized, gap-aware capture segments to the host decoder. Validate NAC,
   talkgroup, source ID and FEC against a known conventional P25 transmitter.
4. Use `dm1701_c6000_unpack_raw36` to test the byte/dibit/polarity candidates,
   then connect the measured choice to `dm1701_p25_audio_push_dibit`. The
   fixed-point IMBE decoder and speaker FIFO now compile freestanding for ARM;
   the final STM32 link, ISR ownership and I2S callback still need board work.
   Host protocol tests cannot establish RF/real-time properties.

A codeplug backup is not a full firmware/calibration backup. Nothing in this
folder flashes the radio, changes firmware, or provides P25 RF transmit support.
See [PROVENANCE.md](PROVENANCE.md) for exact upstream revisions and licensing.
