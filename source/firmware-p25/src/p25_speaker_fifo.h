/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef DM1701_P25_SPEAKER_FIFO_H
#define DM1701_P25_SPEAKER_FIFO_H

#include <stddef.h>
#include <stdint.h>
#include <stdatomic.h>

enum { DM1701_P25_PCM_SAMPLES = 160, DM1701_P25_SPEAKER_FIFO_DEPTH = 4 };

/* Single-producer (P25/radio task), single-consumer (I2S audio task) queue.
 * A full queue drops the newest frame and records the drop; decoder timing is
 * never blocked by a slow speaker task. */
typedef struct {
    int16_t blocks[DM1701_P25_SPEAKER_FIFO_DEPTH][DM1701_P25_PCM_SAMPLES];
    atomic_uint head;
    atomic_uint tail;
    atomic_uint dropped;
} dm1701_p25_speaker_fifo;

void dm1701_p25_speaker_fifo_init(dm1701_p25_speaker_fifo *);
int dm1701_p25_speaker_fifo_push(void *, const int16_t pcm[DM1701_P25_PCM_SAMPLES], size_t samples);
int dm1701_p25_speaker_fifo_pop(dm1701_p25_speaker_fifo *, int16_t pcm[DM1701_P25_PCM_SAMPLES]);
unsigned dm1701_p25_speaker_fifo_dropped(const dm1701_p25_speaker_fifo *);

#endif
