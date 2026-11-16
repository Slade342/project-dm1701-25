/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "p25_speaker_fifo.h"

static void copy_samples(int16_t *dst, const int16_t *src)
{
    for (unsigned i = 0; i < DM1701_P25_PCM_SAMPLES; ++i) dst[i] = src[i];
}

void dm1701_p25_speaker_fifo_init(dm1701_p25_speaker_fifo *f)
{
    if (!f) return;
    for (unsigned b = 0; b < DM1701_P25_SPEAKER_FIFO_DEPTH; ++b)
        for (unsigned i = 0; i < DM1701_P25_PCM_SAMPLES; ++i) f->blocks[b][i] = 0;
    atomic_init(&f->head, 0);
    atomic_init(&f->tail, 0);
    atomic_init(&f->dropped, 0);
}

int dm1701_p25_speaker_fifo_push(void *ctx, const int16_t pcm[DM1701_P25_PCM_SAMPLES], size_t samples)
{
    dm1701_p25_speaker_fifo *f = (dm1701_p25_speaker_fifo *)ctx;
    if (!f || !pcm || samples != DM1701_P25_PCM_SAMPLES) return -1;
    unsigned head = atomic_load_explicit(&f->head, memory_order_relaxed);
    unsigned tail = atomic_load_explicit(&f->tail, memory_order_acquire);
    if (head - tail >= DM1701_P25_SPEAKER_FIFO_DEPTH) {
        atomic_fetch_add_explicit(&f->dropped, 1, memory_order_relaxed);
        return 0;
    }
    copy_samples(f->blocks[head % DM1701_P25_SPEAKER_FIFO_DEPTH], pcm);
    atomic_store_explicit(&f->head, head + 1, memory_order_release);
    return 0;
}

int dm1701_p25_speaker_fifo_pop(dm1701_p25_speaker_fifo *f, int16_t pcm[DM1701_P25_PCM_SAMPLES])
{
    if (!f || !pcm) return -1;
    unsigned tail = atomic_load_explicit(&f->tail, memory_order_relaxed);
    unsigned head = atomic_load_explicit(&f->head, memory_order_acquire);
    if (tail == head) return 0;
    copy_samples(pcm, f->blocks[tail % DM1701_P25_SPEAKER_FIFO_DEPTH]);
    atomic_store_explicit(&f->tail, tail + 1, memory_order_release);
    return 1;
}

unsigned dm1701_p25_speaker_fifo_dropped(const dm1701_p25_speaker_fifo *f)
{
    return f ? atomic_load_explicit(&f->dropped, memory_order_relaxed) : 0;
}
