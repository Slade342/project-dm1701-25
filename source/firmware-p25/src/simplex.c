/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "simplex.h"
#include <string.h>
static void fault(simplex *s){s->io.stop(s->io.ctx);if(s->state==SIMPLEX_RECORD)(void)s->io.record_end(s->io.ctx,0);s->stored=0;s->state=SIMPLEX_FAULT;}
int simplex_init(simplex *s,const simplex_io *io,unsigned mode,uint32_t rx,uint32_t tx){
 if(!s||!io||!io->record_begin||!io->record_append||!io->record_end||!io->play_begin||!io->play_poll||!io->stop||mode>SIMPLEX_P25||rx!=tx)return -1;
 if(rx%10u||!((rx>=136000000u&&rx<=174000000u)||(rx>=400000000u&&rx<=480000000u)))return -1;
 memset(s,0,sizeof *s);s->io=*io;s->mode=(uint8_t)mode;s->max_record_ms=20000;s->hang_ms=500;s->cooldown_ms=2000;s->max_bytes=128000;return 0;
}
int simplex_enable(simplex *s,uint32_t now){
 if(!s||s->state!=SIMPLEX_OFF||!s->max_record_ms||s->max_record_ms>60000||!s->max_bytes||s->hang_ms>5000||s->cooldown_ms<500)return -1;
 s->bytes=0;s->stored=0;s->last_activity=now;s->state=SIMPLEX_LISTEN;return 0;
}
void simplex_disable(simplex *s){
 if(!s)return;
 s->io.stop(s->io.ctx);if(s->state==SIMPLEX_RECORD)(void)s->io.record_end(s->io.ctx,0);s->state=SIMPLEX_OFF;s->stored=0;s->bytes=0;
}
static int finish_record(simplex *s,uint32_t now){
 if(s->io.record_end(s->io.ctx,s->bytes>0)){fault(s);return -1;}
 s->stored=s->bytes>0;s->waiting_since=now;s->state=SIMPLEX_WAIT_END;return 0;
}
void simplex_tick(simplex *s,uint32_t now,int activity,int clear){
 int eligible,result;
 if(!s||s->state==SIMPLEX_OFF||s->state==SIMPLEX_FAULT)return;
 eligible=activity&&(s->mode==SIMPLEX_FM||clear);
 if(s->state==SIMPLEX_LISTEN){
  if(!eligible)return;
  if(s->io.record_begin(s->io.ctx,s->mode)){fault(s);return;}
  s->started=now;s->last_activity=now;s->bytes=0;s->stored=0;s->state=SIMPLEX_RECORD;return;
 }
 if(s->state==SIMPLEX_RECORD){
  if(eligible)s->last_activity=now;
  if((uint32_t)(now-s->started)>=s->max_record_ms||s->bytes>=s->max_bytes||(uint32_t)(now-s->last_activity)>=s->hang_ms){if(finish_record(s,now))return;}
 }
 if(s->state==SIMPLEX_WAIT_END){
  if(activity)s->last_activity=now;
  /* Never start a replay over another active call, including encrypted traffic. */
  if((uint32_t)(now-s->waiting_since)>10000u){s->stored=0;s->cool_since=now;s->state=SIMPLEX_COOLDOWN;return;}
  if((uint32_t)(now-s->last_activity)<s->hang_ms)return;
  if(!s->stored){s->state=SIMPLEX_LISTEN;return;}
  if(s->io.play_begin(s->io.ctx,s->mode)){fault(s);return;}
  s->state=SIMPLEX_PLAY;s->started=now;return;
 }
 if(s->state==SIMPLEX_PLAY){
  result=s->io.play_poll(s->io.ctx);
  if(result<0||(uint32_t)(now-s->started)>s->max_record_ms+2000u){fault(s);return;}
  if(result>0){s->io.stop(s->io.ctx);s->stored=0;s->cool_since=now;s->state=SIMPLEX_COOLDOWN;}return;
 }
 if(s->state==SIMPLEX_COOLDOWN){
  if(activity)s->cool_since=now;
  if((uint32_t)(now-s->cool_since)>=s->cooldown_ms)s->state=SIMPLEX_LISTEN;
 }
}
int simplex_append(simplex *s,const uint8_t *data,size_t n){
 if(!s||s->state!=SIMPLEX_RECORD||!data||!n)return -1;
 if(n>s->max_bytes-s->bytes)return -2;
 if(s->io.record_append(s->io.ctx,data,n)){fault(s);return -1;}
 s->bytes+=(uint32_t)n;return 0;
}
