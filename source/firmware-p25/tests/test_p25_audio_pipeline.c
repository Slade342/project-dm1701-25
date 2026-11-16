/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "p25_audio_pipeline.h"
#include <assert.h>
#include <stdio.h>

static unsigned decoded, samples;
static int decode(void *ctx, const uint16_t u[8], int16_t pcm[160])
{
    (void)ctx; (void)u;
    ++decoded;
    for (unsigned i = 0; i < 160; ++i) pcm[i] = (int16_t)(i - 80);
    return 0;
}
static int speaker(void *ctx, const int16_t pcm[160], size_t n)
{
    (void)ctx; assert(pcm[0] == -80); assert(n == 160); samples += (unsigned)n; return 0;
}
int main(void)
{
    FILE *in = fopen("tests/protocol/vectors/clear-call.bin", "rb");
    assert(in);
    dm1701_p25_audio p;
    assert(dm1701_p25_audio_init(&p, 0x293, 0, NULL, decode, speaker) == 0);
    int byte;
    while ((byte = fgetc(in)) != EOF)
        for (unsigned shift = 6;; shift -= 2) {
            assert(dm1701_p25_audio_push_dibit(&p, (uint8_t)((byte >> shift) & 3)) >= 0);
            if (shift == 0) break;
        }
    fclose(in);
    assert(p.frames_seen == 4 && p.voice_frames == 18 && p.audio_frames == 18);
    assert(decoded == 18 && samples == 2880 && p.codec_errors == 0);
    puts("PASS P25 audio pipeline: stream/FEC/IMBE callback/speaker pacing");
    return 0;
}
