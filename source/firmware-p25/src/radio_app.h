/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef DM1701_RADIO_APP_H
#define DM1701_RADIO_APP_H
#include <stddef.h>
#include <stdint.h>
#define RADIO_CHANNELS 64
enum { RADIO_FM, RADIO_DMR, RADIO_P25 };
enum { KEY_UP=1, KEY_DOWN, KEY_MENU, KEY_BACK, KEY_OK, KEY_SCAN, KEY_NEXT, KEY_PTT_DOWN, KEY_PTT_UP };
enum { FPP_NAME, FPP_MODE, FPP_RX, FPP_TX, FPP_NAC, FPP_TG, FPP_ID, FPP_CC, FPP_SLOT, FPP_SCAN, FPP_RXONLY, FPP_AUDIO, FPP_PROMISCUOUS, FPP_COUNT };
typedef struct {
 char name[17];
 uint32_t rx_hz,tx_hz,source_id;
 uint16_t nac,talkgroup;
 uint8_t mode,rx_only,scan,color_code,time_slot;
 /* Experimental P25 controls. These are configuration flags only until a board
  * supplies a real modem/audio implementation. */
 uint8_t audio, promiscuous;
} radio_channel;
typedef struct {
 void *ctx;
 /* tune must report failure. tx_begin succeeds only with a qualified board path. */
 int (*tune)(void *,const radio_channel *);
 int (*tx_begin)(void *,const radio_channel *);
 void (*tx_end)(void *);
 /* Persist the complete channel array atomically in a board-owned settings slot. */
 int (*save)(void *,const radio_channel *,size_t);
} radio_board;
typedef struct {
 radio_channel channels[RADIO_CHANNELS],edit;
 radio_board board;
 uint32_t deadline;
 uint8_t count,selected,scanning,holding,transmitting,editing,field,name_pos,tuned;
 uint8_t adding,digits_used,rf_busy,promiscuous_scan;
 char digits[12],notice[24];
} radio_app;
int radio_channel_valid(const radio_channel *);
int radio_init(radio_app *,const radio_board *,const radio_channel *,size_t);
/* FPP edits are transactional: cancel changes nothing; persistence failure rolls back. */
int radio_fpp_begin(radio_app *,int add);
int radio_fpp_set(radio_app *,unsigned field,const char *value);
int radio_fpp_commit(radio_app *);
void radio_key(radio_app *,unsigned key,uint32_t now_ms);
void radio_digit(radio_app *,char digit);
/* qualified_activity means decoded, matching channel activity, not merely RSSI. */
void radio_tick(radio_app *,uint32_t now_ms,int qualified_activity);
typedef struct {
 void *ctx;
 void (*rect)(void *,int,int,int,int,uint32_t);
 void (*text)(void *,int,int,unsigned,uint32_t,const char *);
} radio_display;
/* Original professional-radio layout for the DM-1701's visible 160x120 panel. */
void radio_render(const radio_app *,const radio_display *);
#endif
