/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef DM1701_SIMPLEX_H
#define DM1701_SIMPLEX_H
#include <stdint.h>
#include <stddef.h>
enum { SIMPLEX_OFF,SIMPLEX_LISTEN,SIMPLEX_RECORD,SIMPLEX_WAIT_END,SIMPLEX_PLAY,SIMPLEX_COOLDOWN,SIMPLEX_FAULT };
enum { SIMPLEX_FM,SIMPLEX_P25 };
typedef struct {
 /* Callbacks return 0 on success, except play_poll as documented below. */
 void *ctx;
 int (*record_begin)(void *,unsigned mode);
 int (*record_append)(void *,const uint8_t *,size_t);
 int (*record_end)(void *,int keep);
 int (*play_begin)(void *,unsigned mode);
 /* 0 while playing, 1 done, negative on failure. */
 int (*play_poll)(void *);
 void (*stop)(void *);
} simplex_io;
typedef struct {
 simplex_io io;
 uint32_t started,last_activity,waiting_since,cool_since,max_record_ms,hang_ms,cooldown_ms,max_bytes,bytes;
 uint8_t state,mode,stored;
} simplex;
/* HALF DUPLEX store-and-forward only. The board supplies real storage/audio/RF.
 * FM payload is board-defined PCM/ADPCM. P25 payload is clear, validated IMBE
 * plus call metadata, not unnormalized modem RAM. No RF functions are supplied.
 */
int simplex_init(simplex *,const simplex_io *,unsigned mode,uint32_t rx_hz,uint32_t tx_hz);
int simplex_enable(simplex *,uint32_t now_ms);
void simplex_disable(simplex *);
/* activity must match the channel. clear is required for P25 recording. */
void simplex_tick(simplex *,uint32_t now_ms,int activity,int clear);
int simplex_append(simplex *,const uint8_t *,size_t);
#endif
