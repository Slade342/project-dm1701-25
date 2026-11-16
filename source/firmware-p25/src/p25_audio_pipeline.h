/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef DM1701_P25_AUDIO_PIPELINE_H
#define DM1701_P25_AUDIO_PIPELINE_H

#include "p25.h"
#include <stddef.h>
#include <stdint.h>

/* The board supplies these two small, deterministic callbacks. The pipeline
 * owns no heap memory and never writes RF registers or starts a transmitter. */
typedef int (*dm1701_imbe_decode_fn)(void *, const uint16_t parameters[8], int16_t pcm[160]);
typedef int (*dm1701_speaker_write_fn)(void *, const int16_t pcm[160], size_t samples);

typedef struct {
    p25_rx rx;
    void *decode_ctx;
    void *speaker_ctx;
    dm1701_imbe_decode_fn imbe_decode;
    dm1701_speaker_write_fn speaker_write;
    uint32_t frames_seen;
    uint32_t voice_frames;
    uint32_t audio_frames;
    uint32_t rejected_frames;
    uint32_t codec_errors;
    uint16_t expected_nac;
    uint8_t enabled;
} dm1701_p25_audio;

/* NAC is 0..0xfff, or P25_NAC_ANY. max_sync_errors is 0..4. */
int dm1701_p25_audio_init(dm1701_p25_audio *, uint16_t nac, uint8_t max_sync_errors,
                          void *, dm1701_imbe_decode_fn, dm1701_speaker_write_fn);
/* Variant for a board that owns the IMBE state and the speaker/DMA queue as
 * separate objects.  The simple initializer above keeps one context for both
 * callbacks. */
int dm1701_p25_audio_init_split(dm1701_p25_audio *, uint16_t nac, uint8_t max_sync_errors,
                                void *decode_ctx, dm1701_imbe_decode_fn,
                                void *speaker_ctx, dm1701_speaker_write_fn);
/* Push one normalized C4FM dibit (0..3). Return 1 if PCM was emitted, 0 if
 * the stream is still incomplete, and -1 for invalid arguments or callbacks. */
int dm1701_p25_audio_push_dibit(dm1701_p25_audio *, uint8_t dibit);
void dm1701_p25_audio_stop(dm1701_p25_audio *);

#endif
