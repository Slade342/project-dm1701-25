# DM-1701 firmware on macOS

This package supplies a programming application and P25 research code. It does **not** contain a completed P25-capable DM-1701 firmware image. For working FM and DMR today, the established replacement is OpenGD77. Its firmware is a separate upstream download. The research adapter in this package must not be treated as an installable firmware file.

## Before changing firmware

Keep these distinct backups:

| Backup | Purpose |
| --- | --- |
| Original manufacturer codeplug, made with the original CPS | Channels and original settings; normally an `.rdt` file. |
| Original calibration, made with the original CPS | The individual radio's RF calibration; a channel export does not include it. |
| Correct original DM-1701 firmware and its manufacturer loader | A route back to the firmware matching this particular radio. A DM-32 image cannot replace it. |
| Full external-flash backup, made immediately after installing OpenGD77 and **before writing a new OpenGD77 codeplug** | Preserves the original data needed when reverting to stock. |

The OpenGD77 installation instructions call for the first three items before installation, and for a full flash backup immediately afterward. They require restoring that flash backup before reinstalling original firmware. A `dmrconf read` codeplug backup is useful for programming, but is **not** a complete flash or calibration backup. [OpenGD77 installation and recovery instructions](https://www.opengd77.com/archive/viewtopic6560.html?t=2380)

The original CPS and OpenGD77 desktop CPS are Windows applications. If those backups have not been made, use a compatible Windows computer or Windows VM with working USB passthrough for the appropriate CPS. Native macOS programming with qdmr is available; it does not substitute for all manufacturer calibration and recovery functions. Some Windows ARM virtual machines cannot use the required DFU driver. [CPS on Mac discussion](https://www.opengd77.com/archive/viewtopicea56.html?f=12&t=4129)

## Obtain the right OpenGD77 files

Use the **DM-1701** selection, not DM-32, MD-UV380, RT84, or a generic STM32 image. The radios share parts of a firmware family, but their installation selections differ.

- [Official DM-1701 family firmware directory](https://www.opengd77.com/downloads/MDUV380_DM1701/Firmware/Latest/): choose `OpenDM1701.zip` and extract `OpenDM1701.bin`.
- [Official Python STM32 firmware loader directory](https://www.opengd77.com/downloads/PC_CPS/Latest/Linux_loader_for_STM32_radios/): obtain `opengd77_stm32_firmware_loader.py`.
- [Donor firmware download linked by OpenGD77](https://www.passion-radio.com/index.php?controller=attachment&id_attachment=760): extract `MD9600-CSV(2571V5)-V26.45.bin`.

The donor supplies the DMR vocoder to the OpenGD77 installation process. It is not the firmware to install directly on a DM-1701. Without a valid donor, this loader can continue with **FM only**. The donor and codec are not distributed in this package. [OpenGD77 user guide and download references](https://github.com/LibreDMR/OpenGD77_UserGuide/blob/master/OpenGD77_User_Guide.md)

At inspection on November 14, 2026, the Latest page pointed to release directory `20260504_ebd7100bb4c930e6ff0c24202474b5b72e7d6beb`. These hashes identify the files inspected; they are not independent publisher signatures:

| File | SHA-256 |
| --- | --- |
| `OpenDM1701.zip` from that release | `e853e12f52e9b3e5eb801efb42db5d317645183cd7f8555022ae5ba1d4f7357a` |
| Extracted `OpenDM1701.bin`, 804256 bytes | `a09ab4d364d199853204ebdf068ba0886d7e7bb99689f08437aae52104474a7e` |
| Upstream Python loader inspected here | `e2057be3b6c7b6f85ee72190df8a06dd556d36b93738d78ea377d848698312f0` |
| Donor expected by that loader | `d8a653307222e576ee416ab6d4704d14758fa71c1b0e826ffd840f26266cf11f` |

If upstream has changed, read its matching instructions rather than assuming an old hash or command applies to the new files.

## Native macOS loader route

The upstream launcher explicitly includes `Darwin`, and its Python loader uses PyUSB. This route was verified by inspecting the published scripts; **it was not tested with a radio or a Mac in this environment**. The desktop CPS's Windows DFU driver limitation does not establish that a separate PyUSB loader cannot run on macOS. [Upstream launcher source](https://www.opengd77.com/downloads/PC_CPS/Latest/Linux_loader_for_STM32_radios/FirmwareLoader), [Python loader source](https://www.opengd77.com/downloads/PC_CPS/Latest/Linux_loader_for_STM32_radios/opengd77_stm32_firmware_loader.py)

Install Python 3 and libusb using your chosen Mac package manager. For Homebrew, `brew install python libusb`. In a folder containing the three extracted/downloaded files:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pyusb
shasum -a 256 opengd77_stm32_firmware_loader.py OpenDM1701.bin 'MD9600-CSV(2571V5)-V26.45.bin'
```

Compare those hashes with the table above. The upstream donor check must pass for DMR support.

Power the radio off. Attach the DM-1701 programming cable. Hold **PTT and SK1, the small button immediately above PTT**, while turning it on. Its display stays dark and its indicator flashes red/green. Use a charged battery and a stable USB connection. [DM-1701 installation walkthrough](https://www.sa0bux.se/Ham/opengd77/DM1701_install.pdf)

First run the loader's read-only enumeration:

```sh
.venv/bin/python opengd77_stm32_firmware_loader.py --list
```

For the documented DM-1701 bootloader, internal flash starts at **`0x0800C000`**, with one 16 KB page, one 64 KB page and seven 128 KB pages. The interface string is:

```text
@Internal Flash /0x0800C000/01*016Kg,01*064Kg,07*128Kg
```

Confirm this bootloader layout before flashing. Stock firmware's normal programming mode can also appear as USB `0483:DF11`; its internal layout starts at `0x08000000` and has only three 16 KB pages. **USB VID/PID alone does not prove firmware-update mode.** RadioFoundry documents that confusing these modes can damage the bootloader, and the older OpenGD77 Python loader does not enforce its newer descriptor check. If the layout differs or more than one DFU device is listed, stop and resolve the device/mode mismatch. [Measured DM-1701 bootloader descriptors and mode distinction](https://github.com/RadioFoundry/RadioFoundry/blob/947c1398fe85f2c0314f7749888e627270b23679/docs/spec/hardware-dm1701.md#15-bootloader-and-firmware-images)

Once the files, recovery backups and bootloader layout are correct, the upstream flash command is:

```sh
.venv/bin/python opengd77_stm32_firmware_loader.py \
  --model DM-1701 \
  --source 'MD9600-CSV(2571V5)-V26.45.bin' \
  --firmware OpenDM1701.bin
```

This command writes firmware. It is not run by DM-1701 Studio. Verify that its output says it is patching for DMR and identifies DM-1701. Wait for successful completion before disconnecting. If USB access fails, keep the radio in the bootloader and diagnose PyUSB/libusb or use the official Windows loader with the matching driver; do not substitute `dfu-util` commands or a different radio model.

## First boot and programming

Immediately make and retain the full external-flash backup described above through OpenGD77 CPS before writing an OpenGD77 codeplug. The stock `.rdt` format is not an OpenGD77 codeplug. Create a new compatible codeplug or migrate channel information through a supported conversion/export workflow.

For ongoing native Mac programming, the qdmr author's documented installation is `sudo port install qdmr` using MacPorts; it installs the GUI and `dmrconf`. Use qdmr **0.13.0 or newer** for OpenDM1701; firmware revisions can change compatibility, so start with a read/backup and verify the intended file before a write. [Mac installation](https://dm3mat.de/software/qdmr/install.html), [explicit OpenDM1701 support](https://github.com/hmatuschek/qdmr)

In DM-1701 Studio, select the installed firmware correctly. Stock firmware uses the `dm1701` qdmr profile; OpenGD77 on this STM32 radio uses the **`openuv380`** profile for offline verification. For USB operations, let the backend detect the attached radio. Legacy `opengd77` is a different qdmr profile. [qdmr model key](https://github.com/hmatuschek/qdmr/blob/master/lib/openuv380.cc), [DM1701-to-OpenUV380 identification](https://github.com/hmatuschek/qdmr/blob/master/lib/opengd77_interface.cc)

For rollback, follow the upstream recovery instructions: restore the preserved external flash with OpenGD77 still running, then reinstall the original firmware with its matching manufacturer loader. Keep calibration and original codeplug backups available. A generated Studio project or a qdmr codeplug dump alone cannot reconstruct all original radio data.
