# DM-1701 Studio 0.3

Run **DM1701-Studio-Setup-0.3.exe** on 64-bit Windows. Setup installs the app,
Python when needed, its packages, and a desktop shortcut. The title must say
**0.3 EXPERIMENTAL**. Help → About shows the running folder.

Open **Firmware installation → Install P25 voice firmware**. This replaces the
current firmware; keep a full flash/calibration backup and restore tools. The
installer chooses and verifies the image. Follow its bootloader instructions.

After installation, restart normally and reconnect USB. Open **P25 receiver**,
enter the receive frequency and NAC (`any` accepts every NAC), and press **Start
receiving**. Or add/select a P25 channel, then use **Send selected P25 channel**.
The active frequency, NAC and P25 state are saved on the radio. Your full CPS
channel list stays in the saved local codeplug file.

On the radio, hold **#** on an FM channel to turn P25 on/off. Use its VFO/channel
editor to change frequencies. Names starting with `P25` request P25 reception.
The new home screen shows frequency, mode, and recovered NAC/talkgroup/source.

The complete image links P25 error correction and IMBE speech decoding to the
speaker. **Over-air reception, first boot and Windows flashing have not been
verified on hardware.** It attempts clear conventional Phase 1 C4FM within
136–174 or 400–480 MHz. It does not follow trunking control channels, receive
Phase 2/encrypted calls, or transmit P25. Control channels do not carry speech.

**Read radio** uses the native receiver link for Studio firmware. Stock/OpenGD77
FM/DMR codeplugs use separately installed qdmr. Select the actual firmware under
**Read, write & backups**. Failed reads retain diagnostics in the backup folder.

The source-folder alternative is `DM1701-Install.cmd` with Python installed.
Ordinary users can use the setup executable and desktop shortcut.
