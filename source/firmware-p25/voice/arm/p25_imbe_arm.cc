/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Small C ABI wrapper for the fixed-point IMBE decoder. The board owns the
 * object lifetime and supplies the audio DMA callback; no heap is used here. */
#include "imbe_vocoder_impl.h"
#include <new>

#ifndef STUDIO_HOST_CODEC
void *operator new(size_t, void *place) noexcept { return place; }
void operator delete(void *, void *) noexcept {}
#endif

extern "C" int dm1701_imbe_init_arm(void *state)
{
    if (!state) return -1;
    new (state) imbe_vocoder_impl();
    return 0;
}

extern "C" void dm1701_imbe_destroy_arm(void *state)
{
    if (state) static_cast<imbe_vocoder_impl *>(state)->~imbe_vocoder_impl();
}

extern "C" int dm1701_imbe_decode_arm(void *state, const uint16_t parameters[8], int16_t pcm[160])
{
    if (!state || !parameters || !pcm) return -1;
    int16_t frame[8];
    for (unsigned i = 0; i < 8; ++i) frame[i] = (int16_t)parameters[i];
    static_cast<imbe_vocoder_impl *>(state)->imbe_decode(frame, pcm);
    return 0;
}

extern "C" unsigned dm1701_imbe_arm_state_bytes(void)
{
    return (unsigned)sizeof(imbe_vocoder_impl);
}
