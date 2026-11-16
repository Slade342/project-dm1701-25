/* SPDX-License-Identifier: GPL-3.0-or-later
 * The C6000 physical-test RAM layout is documented, but its live DM-1701 bit
 * permutation/polarity is not yet measured.  Keep that uncertainty explicit
 * in a small adapter so the board experiment can change the mapping without
 * touching the P25/FEC/audio core. */
#include "dm1701_c6000_adapter.h"

const dm1701_c6000_symbol_config dm1701_c6000_symbol_default = { 0, 0, 0 };

static uint8_t raw_bit(const uint8_t raw[DM1701_C6000_RAW_BYTES], unsigned bit,
                       uint8_t lsb_first)
{
    unsigned byte = bit >> 3;
    unsigned shift = bit & 7u;
    uint8_t mask = lsb_first ? (uint8_t)(1u << shift) : (uint8_t)(0x80u >> shift);
    return (uint8_t)((raw[byte] & mask) != 0);
}

int dm1701_c6000_unpack_raw36(const uint8_t raw[DM1701_C6000_RAW_BYTES],
                              uint8_t dibits[DM1701_C6000_RAW_DIBITS],
                              const dm1701_c6000_symbol_config *config)
{
    if (!raw || !dibits || !config || config->dibit_xor > 3u ||
        config->lsb_first > 1u || config->dibit_lsb_first > 1u) return -1;
    for (unsigned i = 0; i < DM1701_C6000_RAW_DIBITS; ++i) {
        uint8_t first = raw_bit(raw, 2u * i, config->lsb_first);
        uint8_t second = raw_bit(raw, 2u * i + 1u, config->lsb_first);
        uint8_t dibit = config->dibit_lsb_first
            ? (uint8_t)(first | (uint8_t)(second << 1))
            : (uint8_t)((first << 1) | second);
        dibits[i] = (uint8_t)(dibit ^ config->dibit_xor);
    }
    return 0;
}

int dm1701_c6000_feed_record(dm1701_p25_audio *audio,
                             const dm1701_rx_record *record,
                             const dm1701_c6000_symbol_config *config)
{
    uint8_t dibits[DM1701_C6000_RAW_DIBITS];
    if (!audio || !record || !config || !(record->irq_flags & DM1701_C6000_PHY_IRQ)) return 0;
    if (dm1701_c6000_unpack_raw36(record->ram, dibits, config) < 0) return -1;
    int frames = 0;
    for (unsigned i = 0; i < DM1701_C6000_RAW_DIBITS; ++i) {
        int result = dm1701_p25_audio_push_dibit(audio, dibits[i]);
        if (result < 0) return -1;
        frames += result;
    }
    return frames;
}
