/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "radio_app.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static int tune_fail,save_fail,tx_ready,tunes,tx_calls,ends,saves;
static int tune(void *ctx,const radio_channel *c){(void)ctx;(void)c;tunes++;return tune_fail?-1:0;}
static int save(void *ctx,const radio_channel *c,size_t n){(void)ctx;(void)c;(void)n;saves++;return save_fail?-1:0;}
static int tx(void *ctx,const radio_channel *c){(void)ctx;(void)c;tx_calls++;return tx_ready?0:-1;}
static void end(void *ctx){(void)ctx;ends++;}
int main(void){
 radio_app a;radio_channel c[3]={
  {"County dispatch",155000000,155000000,1234567,0x293,9,RADIO_P25,1,1,1,1,1,0},
  {"Local FM",145500000,145500000,1234567,0x293,9,RADIO_FM,1,0,1,1,1,0},
  {"P25 simplex",433450000,433450000,1234567,0x293,10,RADIO_P25,0,1,1,1,1,1}};
 radio_board b={NULL,tune,tx,end,save};
 assert(radio_init(&a,&b,c,3)==0);
 /* Scan excludes nonmembers, holds matching traffic, resumes after hang time. */
 radio_key(&a,KEY_SCAN,100);radio_tick(&a,100,0);assert(a.selected==2);
 radio_tick(&a,110,1);radio_tick(&a,1609,0);assert(a.selected==2);
 radio_tick(&a,1610,0);assert(a.selected==0);
 /* Tick deadlines remain correct across the uint32 rollover. */
 a.deadline=0xfffffff0u;radio_tick(&a,0xfffffff1u,0);assert(a.selected==2);
 radio_tick(&a,0x20u,0);assert(a.selected==2);radio_tick(&a,0x70u,0);assert(a.selected==0);
 assert(radio_fpp_begin(&a,0)==0);assert(!a.scanning);
 assert(radio_fpp_set(&a,FPP_NAC,"F7E")==0);assert(radio_fpp_set(&a,FPP_RX,"155.12345")==0);
 assert(radio_fpp_set(&a,FPP_TX,"800.000")==-1);assert(radio_fpp_set(&a,FPP_RX,"155.123451")==-1);
 assert(radio_fpp_set(&a,FPP_ID,"16777216")==-1);assert(radio_fpp_set(&a,FPP_NAC,"1000")==-1);
 radio_key(&a,KEY_BACK,0);assert(a.channels[0].nac==0x293);
 assert(radio_fpp_begin(&a,0)==0);assert(radio_fpp_set(&a,FPP_NAME,"My channel")==0);
 save_fail=1;assert(radio_fpp_commit(&a)==-1);assert(!strcmp(a.channels[0].name,"County dispatch"));assert(a.editing);
 save_fail=0;assert(radio_fpp_commit(&a)==0);assert(!strcmp(a.channels[0].name,"My channel"));
 assert(radio_fpp_begin(&a,1)==0);assert(a.edit.rx_only);assert(radio_fpp_commit(&a)==0);assert(a.count==4);
 radio_key(&a,KEY_PTT_DOWN,0);assert(!a.transmitting&&!tx_calls);
 a.selected=2;radio_key(&a,KEY_PTT_DOWN,0);assert(!a.transmitting&&tx_calls==1);
 tx_ready=1;radio_key(&a,KEY_PTT_DOWN,0);assert(a.transmitting);
 radio_key(&a,KEY_MENU,0);assert(!a.editing);radio_key(&a,KEY_PTT_UP,0);assert(!a.transmitting&&ends==1);
 tune_fail=1;radio_key(&a,KEY_UP,0);assert(!a.tuned);radio_key(&a,KEY_PTT_DOWN,0);assert(tx_calls==2);
 printf("FPP transactions, scan hold/rollover, RX-only/PTT, failed tuning: passed (%d tunes, %d saves)\n",tunes,saves);return 0;
}
