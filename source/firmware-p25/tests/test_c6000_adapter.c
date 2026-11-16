/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "dm1701_c6000_adapter.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned decoded, samples;
static int decode(void *ctx, const uint16_t u[8], int16_t pcm[160])
{
    (void)ctx; (void)u; ++decoded;
    memset(pcm, 0, 160 * sizeof *pcm);
    return 0;
}
static int speaker(void *ctx, const int16_t pcm[160], size_t n)
{
    (void)ctx; (void)pcm; assert(n == 160); ++samples; return 0;
}

int main(void)
{
    /* A small mapping sanity check: 0xB1 is 10110001 -> 2,3,0,1. */
    uint8_t raw[DM1701_C6000_RAW_BYTES] = {0};
    uint8_t dibits[DM1701_C6000_RAW_DIBITS] = {0};
    raw[0] = 0xB1;
    assert(dm1701_c6000_unpack_raw36(raw, dibits, &dm1701_c6000_symbol_default) == 0);
    assert(dibits[0] == 2 && dibits[1] == 3 && dibits[2] == 0 && dibits[3] == 1);
    dm1701_c6000_symbol_config reverse = { 1, 1, 2 };
    assert(dm1701_c6000_unpack_raw36(raw, dibits, &reverse) == 0);
    assert(dibits[0] == 3 && dibits[1] == 2 && dibits[2] == 1 && dibits[3] == 0);

    FILE *in = fopen("tests/protocol/vectors/clear-call.bin", "rb");
    assert(in);
    dm1701_p25_audio audio;
    assert(dm1701_p25_audio_init(&audio, 0x293, 0, NULL, decode, speaker) == 0);
    unsigned sequence = 0;
    for (;;) {
        dm1701_rx_record record;
        memset(&record, 0, sizeof record);
        record.sequence = sequence++;
        record.irq_flags = DM1701_C6000_PHY_IRQ;
        size_t got = fread(record.ram, 1, sizeof record.ram, in);
        if (got == 0) break;
        if (got < sizeof record.ram) memset(record.ram + got, 0, sizeof record.ram - got);
        assert(dm1701_c6000_feed_record(&audio, &record, &dm1701_c6000_symbol_default) >= 0);
    }
    fclose(in);
    assert(audio.frames_seen == 4 && audio.audio_frames == 18 && decoded == 18 && samples == 18);
    dm1701_rx_record ignored = {0};
    assert(dm1701_c6000_feed_record(&audio, &ignored, &dm1701_c6000_symbol_default) == 0);
    puts("PASS C6000 adapter: packed dibits, polarity/order controls, streamed P25 audio");
    return 0;
}
