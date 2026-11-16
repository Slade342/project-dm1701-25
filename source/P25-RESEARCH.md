# P25 on the DM-1701: research status

The DM-32/Open25 example is relevant. It shows that a radio sold for DMR can gain P25 when firmware can access its physical modem and run the required protocol and voice codec. It does not supply a ready-to-flash DM-1701 image. The work in this package is an experimental **receive-side port foundation**, not an operational three-mode firmware release.

## What changed the feasibility assessment

OpenGD77's older unsupported-features post names P25 and explains that its developers could not access raw decoded 4FSK data using their available documentation. It also leaves open the possibility of undocumented chip functions. That is evidence about OpenGD77's implementation and knowledge at the time, not a proof that P25 is physically impossible on the DM-1701. [Original developer statement](https://www.opengd77.com/archive/viewtopic38a9.html?f=7&p=11632&sid=&t=1317)

More recent RadioFoundry source documents an HR_C6000 physical-layer BER mode and reports bench transmission of caller-supplied 288-bit blocks. Its register reference describes raw receive blocks and configurable receive sync patterns. Those are concrete reasons to investigate a software port. Neither source establishes completed DM-1701 P25 interoperability. [C6000 modem notes](https://github.com/RadioFoundry/RadioFoundry/blob/947c1398fe85f2c0314f7749888e627270b23679/docs/spec/modem-hrc6000.md), [register reference](https://github.com/RadioFoundry/RadioFoundry/blob/947c1398fe85f2c0314f7749888e627270b23679/docs/spec/hrc6000-registers.md)

## Open25 code that can be reused

Open25 **Classic** publishes source for conventional P25 together with FM and DMR. Its separate **Next** edition's source remains unreleased at the inspected revision. Classic itself remains an alpha/release-candidate project and reports incomplete RF qualification, so its host tests do not establish interoperability on another radio. [Open25 project status](https://github.com/tylerwatt12/Open25-DM32/blob/19420686920fdd37a6554285d0aa5f5d5ce8a36f/README.md)

| Layer | DM-32 implementation | DM-1701 requirement |
| --- | --- | --- |
| CPU and firmware platform | C-SKY/HR_C7000 platform, RadioFoundry DM32 board | ARM Cortex-M4/STM32F405 board integration |
| Physical modem | HR_C7000 memory-mapped registers and interrupts | HR_C6000 paged SPI registers, buffers and interrupt handlers |
| P25 framing/FEC | Portable C in `src/p25/` | Reuse with captured-stream and independent-vector tests |
| Speech | Software IMBE, third-party codec dependencies | ARM build, memory and real-time audio validation |
| Channels/UI/storage | Classic DM32 channel format and radio UI | Deliberate DM1701 firmware/CPS extension with migration rules |

The C7000 register addresses, interrupt vectors and DM32 binary cannot be copied to a C6000 radio. Portable protocol code is a useful starting point. Open25's build recipe and source locking make that separation visible. [Classic build instructions](https://github.com/tylerwatt12/Open25-DM32/blob/19420686920fdd37a6554285d0aa5f5d5ce8a36f/BUILD.md), [C7000 native adapter](https://github.com/tylerwatt12/Open25-DM32/blob/19420686920fdd37a6554285d0aa5f5d5ce8a36f/integration/radiofoundry/native/hrc_native_chip.c)

## C6000 receive evidence

The following are a **research register map**, not commands for an end user to send to a connected radio. Existing firmware must first give up modem/audio ownership and preserve state for restoration.

| Function | Evidence from the C6000 register reference |
| --- | --- |
| Continuous physical-layer mode | System page register `0x10 = 0x02` in the manual's BER-test recipe |
| Receive enabled, physical test decode mode | System `0x40 = 0x40`; bit 7, TX synchronization enable, remains clear |
| Receive/test start | System `0x41 = 0x41` in that recipe |
| Data-ready event | System `0x82` bit 0; enable with mask `0x81` bit 0, acknowledge through `0x83` bit 0 |
| Raw receive data | RX RAM, data page, offset `0x30`, 36 bytes |
| Physical-test IF | System `0x01=xxxx0000`, `0x07..0x09=0x0BD954` (455 kHz) |
| Physical-test start | System `0x10=0x02`, `0x40=0x40`, `0x41=0x41` |

Reference sections 2.2, 3.9–3.12, 4 and 6.4 describe these fields. Its physical blocks contain DMR-shaped field timing, so assuming each 36-byte block is already in over-the-air P25 bit order would be incorrect. The candidate receiver must establish byte order, dibit order, polarity, field layout and continuity from actual captures. [Pinned register reference](https://github.com/RadioFoundry/RadioFoundry/blob/947c1398fe85f2c0314f7749888e627270b23679/docs/spec/hrc6000-registers.md)

## What the supplied experiment establishes

The accompanying research module reuses upstream framing/FEC logic with a receive-only C6000 adapter and host replay tests. It now includes real software IMBE encode/decode, offline P25 transmit-frame assembly, transactional FPP, scanning, an original radio display renderer, and a store-and-forward FM/P25 simplex controller. The generated-audio test traverses PCM, IMBE, P25 frames, receive decoding and PCM. Read its own README for exact commands, artifacts and test results. It supplies no working RF transmitter and no complete flash image. The new FPP/scan/simplex components still require board integration; the codeplug app cannot install or enable them on OpenGD77.

Host compilation and replay can establish that code builds and recognizes controlled bitstreams. They cannot establish that a real C6000 supplies those bitstreams, that decoded speech reaches the DM1701 speaker in real time, or that original FM/DMR behavior survives mode changes.

The package now also contains a complete **capture-lab** image under `firmware-lab`, compiled from the pinned RadioFoundry tree with AUDIO_PROBE enabled. This is distinct from the new P25 code: it exposes the existing board's raw-access debug functions for the first physical experiment. A guided Windows installer checks its manifest and downloads the matching codec/key source. The new capture script saves raw36 blocks and restores receive registers while leaving a RAM-only TX block until restart. Compilation, vectors, memory ranges and an offline installer plan were checked; boot, USB flashing and RF behavior have not been tested. This is not a completed P25 voice build.

## Remaining work for a usable radio release

1. Integrate the adapter into a specifically pinned DM1701 firmware tree, including exclusive interrupt ownership, PA-off enforcement and state restoration.
2. Capture real C6000 receive blocks from independently generated conventional P25 Phase 1 C4FM signals. Resolve reordering, polarity, timing, signal quality and stream gaps.
3. Validate sync/NID decoding, NAC filtering, frame types, voice FEC and IMBE against independent known-good captures; measure frame losses and bit errors.
4. Build and profile IMBE on the STM32F405, then connect its PCM output to actual speaker playback without overruns. Test repeated calls and mode changes.
5. Define P25 channel storage and CPS fields, keeping unsupported modes from being silently converted to FM or DMR.
6. Separately implement and measure any future transmitter: modulation, symbol rate/deviation, filtering, buffer timing and interoperability. A receive-side experiment does not authorize claims about transmit support.

Initial scope is conventional unencrypted **P25 Phase 1 C4FM** within the radio's supported bands. Phase 2, trunking, LSM/CQPSK, encryption and 700/800 MHz capability are not implemented by this package. P25 does not extend the DM1701's RF hardware coverage.

## Inspected source revisions

| Project | Commit |
| --- | --- |
| [Open25-DM32](https://github.com/tylerwatt12/Open25-DM32/tree/19420686920fdd37a6554285d0aa5f5d5ce8a36f) | `19420686920fdd37a6554285d0aa5f5d5ce8a36f` |
| [RadioFoundry](https://github.com/RadioFoundry/RadioFoundry/tree/947c1398fe85f2c0314f7749888e627270b23679) | `947c1398fe85f2c0314f7749888e627270b23679` |

Open25 additions are GPL-3.0-or-later. Preserve their notices and the licenses of their codec/protocol dependencies; RadioFoundry's underlying MIT license does not remove the Open25 derivative's GPL obligations. Consult the research directory's third-party notices before redistributing a combined firmware. Source inspection and this port foundation are a best effort toward P25, not a claim of successful radio testing.
