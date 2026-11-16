# IMBE encode/decode workbench

This builds a real software IMBE encoder and decoder using Pavel Yazev's fixed-point implementation from nostar/imbe_vocoder at commit `03423cb00b8e9ba1be164493e8b98b5bd7c1508c`, the same dependency pinned by Open25 Classic. The vendor source retains its notices; the GPL-3.0-or-later license in the parent folder applies. No proprietary donor codec is included.

Run `make test` here after `make` in the parent directory. C++14 and Python 3 are required. macOS Command Line Tools supply a compiler.

```sh
./build/p25-voice encode input.pcm vectors.be16
../build/p25-txfile --imbe vectors.be16 --out call.bin --nac 293 --tg 9 --id 1234567
./build/p25-voice receive call.bin received.pcm
```

PCM is mono, 8000 samples/second, signed 16-bit little endian. Each PCM frame has 160 samples; each output vector has eight big-endian 16-bit words. `p25-txfile` needs a multiple of nine vectors and builds HDU, alternating LDU1/LDU2 and TDU. It generates packed on-air bits, with no USB or RF access. `receive` runs streaming P25 framing/FEC and emits PCM only for metadata marked unencrypted; untrusted metadata and large detected voice error counts produce silence. It does not decrypt signals.

The smoke test encodes 18 frames of generated 440 Hz audio, builds a call, decodes it through P25 framing/FEC and the speech codec, checks audio length and nonzero output, and rejects truncated audio. It is a real executable round trip, not a speech-quality or RF-interoperability test. Codec artifacts and quality remain subject to independent recorded-speech evaluation.

`make -C .. arm-p25` now cross-compiles the fixed-point decoder and a placement-new
C ABI wrapper for `thumb-freestanding-eabi`; it reports the combined code size
and rejects unresolved symbols. The wrapper is still a relocatable component,
not a qualified STM32 image. Before radio integration, measure CPU/stack use on
the F405, provide bounded 20 ms audio pacing (the parent speaker FIFO supplies
the queue), handle loss/concealment, and connect real I2S/DAC DMA. The upstream
fixed-point implementation assumes arithmetic behavior typical of its supported
compilers; the host build uses `-fwrapv`. An x86 build or ARM protocol-object
build does not establish real-time speech operation on a DM-1701.
