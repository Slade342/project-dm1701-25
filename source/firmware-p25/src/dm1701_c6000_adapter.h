/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef DM1701_C6000_ADAPTER_H
#define DM1701_C6000_ADAPTER_H

#include <stdint.h>
#include "dm1701_rx_probe.h"
#include "p25_audio_pipeline.h"

/* The documented HRC6000 physical-layer test produces 36 packed bytes
 * (288 bits) at page 2:0x030 for each receive completion.  That is 144
 * dibits when the modem's bit order has been measured. */
enum {
    DM1701_C6000_RAW_BYTES = 36,
    DM1701_C6000_RAW_DIBITS = 144,
    DM1701_C6000_PHY_IRQ = 1
};

typedef struct {
    /* 0 = byte MSB first (the documented SPI/RAM convention), 1 = LSB first. */
    uint8_t lsb_first;
    /* 0 = first bit is dibit bit 1, 1 = first bit is dibit bit 0. */
    uint8_t dibit_lsb_first;
    /* XOR applied after forming each dibit; 2 is the usual C4FM polarity flip. */
    uint8_t dibit_xor;
} dm1701_c6000_symbol_config;

/* Canonical configuration pending a live-radio ordering measurement. */
extern const dm1701_c6000_symbol_config dm1701_c6000_symbol_default;

/* Convert one physical-test RAM block into normalized dibits.  No allocation,
 * register access, or RF action occurs. */
int dm1701_c6000_unpack_raw36(const uint8_t raw[DM1701_C6000_RAW_BYTES],
                              uint8_t dibits[DM1701_C6000_RAW_DIBITS],
                              const dm1701_c6000_symbol_config *config);

/* Feed one IRQ record into the bounded P25/FEC/IMBE/speaker pipeline.  The
 * return value is the number of complete P25 frames emitted by this record;
 * zero is normal while a frame is accumulating. */
int dm1701_c6000_feed_record(dm1701_p25_audio *audio,
                             const dm1701_rx_record *record,
                             const dm1701_c6000_symbol_config *config);

#endif
