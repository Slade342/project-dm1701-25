/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "p25_speaker_fifo.h"
#include <assert.h>
#include <stdio.h>

int main(void)
{
    dm1701_p25_speaker_fifo f;
    int16_t in[DM1701_P25_PCM_SAMPLES], out[DM1701_P25_PCM_SAMPLES];
    for (unsigned i = 0; i < DM1701_P25_PCM_SAMPLES; ++i) in[i] = (int16_t)i;
    dm1701_p25_speaker_fifo_init(&f);
    for (unsigned n = 0; n < DM1701_P25_SPEAKER_FIFO_DEPTH; ++n) {
        in[0] = (int16_t)n;
        assert(dm1701_p25_speaker_fifo_push(&f, in, DM1701_P25_PCM_SAMPLES) == 0);
    }
    assert(dm1701_p25_speaker_fifo_push(&f, in, DM1701_P25_PCM_SAMPLES) == 0);
    assert(dm1701_p25_speaker_fifo_dropped(&f) == 1);
    for (unsigned n = 0; n < DM1701_P25_SPEAKER_FIFO_DEPTH; ++n) {
        assert(dm1701_p25_speaker_fifo_pop(&f, out) == 1);
        assert(out[0] == (int16_t)n);
    }
    assert(dm1701_p25_speaker_fifo_pop(&f, out) == 0);
    puts("PASS speaker FIFO: bounded producer/consumer pacing and drop accounting");
    return 0;
}
