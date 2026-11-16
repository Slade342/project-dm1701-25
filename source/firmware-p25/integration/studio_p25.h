/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef STUDIO_P25_H
#define STUDIO_P25_H
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include "radio/radio.h"
typedef struct {
 uint8_t enabled,locked,mapping,fault,scan_mode;
 uint16_t nac,talkgroup;
 uint32_t source_id,blocks,frames,audio_frames,overruns,bad_nids,decode_us;
} studio_p25_view_t;
bool studio_p25_active(void);
void studio_p25_toggle(void);
void studio_p25_view(studio_p25_view_t *);
/* Radio task only: serialization with all RF/codec mode transitions. */
void studio_p25_poll(const radio_view_t *);
void studio_p25_leave(void);
size_t studio_p25_command(const uint8_t *,uint16_t,uint8_t *,size_t);
#endif
