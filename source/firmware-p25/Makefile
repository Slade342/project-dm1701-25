# SPDX-License-Identifier: GPL-3.0-or-later
CC ?= cc
PYTHON ?= python3
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -pedantic
CPPFLAGS += -Ivendor/open25 -Ivendor/radiofoundry -Isrc
.PHONY: all test clean arm-check arm-p25 windows-capture
all: build/p25-capture build/p25-txfile build/radio-layout build/libdm1701-p25.a
build:
	mkdir -p build
build/p25.o: vendor/open25/p25.c vendor/open25/p25.h vendor/open25/golay_table.inc | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
build/p25-audio-pipeline.o: src/p25_audio_pipeline.c src/p25_audio_pipeline.h vendor/open25/p25.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
build/c6000-symbol-adapter.o: src/dm1701_c6000_adapter.c src/dm1701_c6000_adapter.h src/dm1701_rx_probe.h src/p25_audio_pipeline.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
build/p25-speaker-fifo.o: src/p25_speaker_fifo.c src/p25_speaker_fifo.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
build/probe.o: src/dm1701_rx_probe.c src/dm1701_rx_probe.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
build/bridge.o: src/radiofoundry_bridge.c src/radiofoundry_bridge.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
build/radio-app.o: src/radio_app.c src/radio_app.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
build/simplex.o: src/simplex.c src/simplex.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
build/libdm1701-p25.a: build/p25.o build/p25-audio-pipeline.o build/c6000-symbol-adapter.o build/p25-speaker-fifo.o build/probe.o build/bridge.o build/radio-app.o build/simplex.o
	$(AR) rcs $@ $^
build/p25-capture: src/p25_capture.c build/p25.o
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
build/p25-txfile: src/p25_txfile.c build/p25.o
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
build/radio-layout: tools/radio_layout.c build/radio-app.o
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
build/test-radio-app: tests/test_radio_app.c build/radio-app.o
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
build/test-p25-audio: tests/test_p25_audio_pipeline.c build/p25-audio-pipeline.o build/p25.o
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
build/test-c6000-adapter: tests/test_c6000_adapter.c build/c6000-symbol-adapter.o build/p25-audio-pipeline.o build/p25.o
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
build/test-speaker-fifo: tests/test_speaker_fifo.c build/p25-speaker-fifo.o
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
build/test-simplex: tests/test_simplex.c build/simplex.o
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
build/test-probe: tests/test_probe.c src/dm1701_rx_probe.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -DDM1701_EXPERIMENTAL_RX=1 $^ -o $@
build/test-probe-disabled: tests/test_probe_disabled.c src/dm1701_rx_probe.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
build/test-bridge: tests/test_bridge.c src/radiofoundry_bridge.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@
test: all build/test-probe build/test-probe-disabled build/test-bridge build/test-radio-app build/test-simplex build/test-p25-audio build/test-c6000-adapter build/test-speaker-fifo
	$(PYTHON) tests/test_protocol.py
	./build/test-probe
	./build/test-probe-disabled
	./build/test-bridge
	./build/test-radio-app
	./build/test-simplex
	./build/test-p25-audio
	./build/test-c6000-adapter
	./build/test-speaker-fifo
	$(PYTHON) tests/test_capture.py
arm-check:
	$(PYTHON) tools/arm_check.py
arm-p25:
	$(PYTHON) tools/build_arm_p25.py --zig "$${DM1701_ZIG:?Set DM1701_ZIG to the Zig executable}"
windows-capture:
	DM1701_ZIG="$${DM1701_ZIG:?Set DM1701_ZIG to the Zig executable}" $(PYTHON) tools/build_windows_capture.py
clean:
	rm -rf build
