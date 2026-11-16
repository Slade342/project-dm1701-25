/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "simplex.h"
#include <assert.h>
#include <stdio.h>
static int recordings,plays,stops,fail_append,done;
static int begin(void *p,unsigned m){(void)p;(void)m;recordings++;return 0;}
static int append(void *p,const uint8_t *d,size_t n){(void)p;(void)d;(void)n;return fail_append?-1:0;}
static int end(void *p,int keep){(void)p;(void)keep;return 0;}
static int play(void *p,unsigned m){(void)p;(void)m;plays++;return 0;}
static int poll(void *p){(void)p;return done;}
static void stop(void *p){(void)p;stops++;}
int main(void){
 simplex s;simplex_io io={NULL,begin,append,end,play,poll,stop};uint8_t data[16]={0};
 assert(simplex_init(&s,&io,SIMPLEX_P25,433450000,433460000)==-1);
 assert(simplex_init(&s,&io,SIMPLEX_P25,433450000,433450000)==0);
 assert(s.state==SIMPLEX_OFF);assert(simplex_enable(&s,0)==0);
 simplex_tick(&s,1,1,0);assert(recordings==0); /* encrypted/unknown traffic */
 simplex_tick(&s,10,1,1);assert(s.state==SIMPLEX_RECORD&&recordings==1);
 assert(simplex_append(&s,data,sizeof data)==0);
 simplex_tick(&s,200,1,1);simplex_tick(&s,699,0,1);assert(plays==0);
 simplex_tick(&s,700,0,1);assert(s.state==SIMPLEX_PLAY&&plays==1);
 simplex_tick(&s,710,1,1);assert(recordings==1); /* never record own replay */
 done=1;simplex_tick(&s,720,0,1);assert(s.state==SIMPLEX_COOLDOWN&&stops==1);
 simplex_tick(&s,2000,1,1);simplex_tick(&s,3999,0,1);assert(recordings==1);
 simplex_tick(&s,4000,0,1);assert(s.state==SIMPLEX_LISTEN);
 simplex_tick(&s,4100,1,1);fail_append=1;assert(simplex_append(&s,data,sizeof data)==-1);assert(s.state==SIMPLEX_FAULT&&stops==2);
 simplex_disable(&s);fail_append=0;done=0;
 assert(simplex_enable(&s,0xfffffff0u)==0);simplex_tick(&s,0xfffffff0u,1,1);assert(simplex_append(&s,data,16)==0);
 simplex_tick(&s,0x200u,0,1);assert(s.state==SIMPLEX_PLAY); /* rollover-safe hang */
 simplex_disable(&s);
 assert(simplex_init(&s,&io,SIMPLEX_FM,145500000,145500000)==0);s.max_record_ms=1000;s.max_bytes=16;
 assert(simplex_enable(&s,0)==0);simplex_tick(&s,1,1,0);assert(s.state==SIMPLEX_RECORD);
 assert(simplex_append(&s,data,16)==0);assert(simplex_append(&s,data,1)==-2);
 simplex_tick(&s,2,1,0);assert(s.state==SIMPLEX_WAIT_END);assert(plays==2);
 simplex_tick(&s,9000,1,0);assert(s.state==SIMPLEX_WAIT_END);
 simplex_tick(&s,11000,1,0);assert(s.state==SIMPLEX_COOLDOWN); /* busy channel timeout */
 printf("PASS simplex P25/FM: clear traffic, bounded recording, end-of-call replay, half-duplex, cooldown, bus failure, timer rollover\n");return 0;
}
