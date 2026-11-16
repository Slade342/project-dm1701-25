/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "p25_audio_pipeline.h"
#include "p25_runtime.h"

int dm1701_p25_audio_init(dm1701_p25_audio *p, uint16_t nac, uint8_t errors,
                          void *ctx, dm1701_imbe_decode_fn decode,
                          dm1701_speaker_write_fn speaker)
{
    return dm1701_p25_audio_init_split(p, nac, errors, ctx, decode, ctx, speaker);
}

int dm1701_p25_audio_init_split(dm1701_p25_audio *p, uint16_t nac, uint8_t errors,
                                void *decode_ctx, dm1701_imbe_decode_fn decode,
                                void *speaker_ctx, dm1701_speaker_write_fn speaker)
{
    if (!p || !decode || !speaker || (nac > 0xfff && nac != P25_NAC_ANY)) return -1;
    memset(p, 0, sizeof *p);
    p->decode_ctx = decode_ctx;
    p->speaker_ctx = speaker_ctx;
    p->imbe_decode = decode;
    p->speaker_write = speaker;
    p->expected_nac = nac;
    p->enabled = 1;
    p25_rx_init(&p->rx, nac, errors > 4 ? 4 : errors);
    return 0;
}

static int voice_duid(uint8_t duid)
{
    return duid == P25_DUID_LDU1 || duid == P25_DUID_LDU2;
}

int dm1701_p25_audio_push_dibit(dm1701_p25_audio *p, uint8_t dibit)
{
    p25_decoded frame;
    if (!p || !p->enabled || dibit > 3) return -1;
    if (p25_rx_push_dibit(&p->rx, dibit) != 1) return 0;
    p->frames_seen++;
    if (p25_decode_frame(p->rx.frame, p25_frame_bytes(p->rx.nid.duid), &frame) < 0 ||
        !frame.metadata_valid || !frame.clear_voice || !voice_duid(frame.nid.duid)) {
        p->rejected_frames++;
        return 0;
    }
    p->voice_frames += P25_IMBE_FRAMES;
    for (unsigned i = 0; i < P25_IMBE_FRAMES; ++i) {
        int16_t pcm[160];
        if (frame.voice_corrected_bits[i] > 9 || p->imbe_decode(p->decode_ctx, frame.imbe[i], pcm) < 0) {
            p->codec_errors++;
            continue;
        }
        if (p->speaker_write(p->speaker_ctx, pcm, 160) < 0) {
            p->enabled = 0;
            return -1;
        }
        p->audio_frames++;
    }
    return 1;
}

void dm1701_p25_audio_stop(dm1701_p25_audio *p)
{
    if (p) p->enabled = 0;
}
