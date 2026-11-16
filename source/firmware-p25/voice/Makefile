# SPDX-License-Identifier: GPL-3.0-or-later
CXX ?= c++
CC ?= cc
SOURCES = $(wildcard vendor/*.cc)
OBJECTS = $(patsubst vendor/%.cc,build/%.o,$(SOURCES))
.PHONY: all test clean
all: build/p25-voice
build:
	mkdir -p build
build/%.o: vendor/%.cc | build
	$(CXX) -O2 -std=c++14 -fwrapv -Ivendor -c $< -o $@
build/p25.o: ../vendor/open25/p25.c | build
	$(CC) -O2 -std=c11 -I../vendor/open25 -c $< -o $@
build/p25-voice: codec_cli.cc $(OBJECTS) build/p25.o
	$(CXX) -O2 -std=c++14 -fwrapv -Ivendor -I../vendor/open25 $^ -o $@
test: all
	python3 test_voice.py
clean:
	rm -rf build
