# Windows x64 desktop speech test

`p25-voice.exe` is a cross-compiled 64-bit Windows console application. It performs
P25 Phase 1 framing/FEC and IMBE audio processing without USB access or RF output.
It has not been executed on Windows here. The equivalent native decoder passed
the known-speech test on Linux. The generated Windows PE header and imports were
inspected; it uses Windows Universal CRT and Kernel32, without an external C++ DLL.

Run `Test-P25-Speech.cmd` from the project root. It decodes the synthetic known
speech bitstream and plays a WAV on the **computer**, not the radio. The expected
phrase is: "This is a P twenty five speech decoder test. The decoder is running
on the computer." The WAV and a JSON report are saved under `voice/results`.

The CPS also offers **Play known P25 speech test (PC)** and **Decode P25 bit capture
to WAV**. The latter requires demodulated, packed on-air P25 Phase 1 voice bits.
It rejects raw C6000 JSONL, IQ and WAV. A trunking control channel is not a voice
capture. This tool does not decrypt encrypted calls.

All codec and protocol sources are supplied alongside this binary. They retain
their GPL notices. Install Zig and run `python build_windows.py` from the voice
directory to rebuild. The supplied binary used Zig 0.17.1, target x86_64-windows-gnu, C++14, -O2 and -fwrapv.
