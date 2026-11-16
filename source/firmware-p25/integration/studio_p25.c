/* SPDX-License-Identifier: GPL-3.0-or-later
 * Experimental DM-1701 conventional P25 receive integration. */
#include "studio_p25.h"
#include "board.h"
#include "hal_time.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "debuglink/dl_frame.h"
#include "debuglink/dl_fmt.h"
#include "p25.h"
#include "settings/settings.h"
#include <string.h>

extern int dm1701_imbe_init_arm(void *);
extern int dm1701_imbe_decode_arm(void *,const uint16_t[8],int16_t[160]);
extern unsigned dm1701_imbe_arm_state_bytes(void);

#define RAW_QUEUE 16u
#define PCM_QUEUE 16u
static studio_p25_view_t info;
static volatile uint8_t requested,change;
static uint16_t requested_nac=0xffff;
static uint8_t requested_mapping=255;
/* 0 = NAC/TG policy, 1 = NAC-only, 2 = no NAC/TG filter.  The latter also
 * asks the stock zone scanner to walk the selected P25 channels. */
static uint8_t requested_scan_mode=2;
static uint32_t tuned_hz;
static uint32_t requested_hz;
static volatile uint32_t receiver_hz;
static volatile uint32_t last_frame_ms;
static bool active,stream_on;
static bool settings_loaded;
static QueueHandle_t raw_queue;
static TaskHandle_t worker;
static uint8_t saved[9];
static const uint8_t regs[9]={0x01,0x10,0x40,0x41,0x5f,0x81,0x22,0xe0,0xe2};
static volatile uint32_t generation;
typedef struct {uint32_t gen;uint8_t raw[36];} raw_block;
static p25_rx candidates[8];
static p25_decoded frame;
static uint64_t codec_state[768]; /* 6144 bytes, queried before construction */
static int16_t audio_pcm[PCM_QUEUE][160];
static volatile uint32_t pcm_head,pcm_tail;
static bool pcm_primed;
static uint32_t worker_generation;
static int selected=-1;

bool studio_p25_active(void) {return active || requested;}
void studio_p25_toggle(void) {requested=!studio_p25_active();change=1;}
void studio_p25_view(studio_p25_view_t *out)
{
 taskENTER_CRITICAL();*out=info;taskEXIT_CRITICAL();
}
static bool reg(uint8_t r,uint8_t *v,bool write)
{return board.audio_tap && board.audio_tap->modem_reg && board.audio_tap->modem_reg(4,r,v,write);}
static bool wr(uint8_t r,uint8_t v) {return reg(r,&v,true);}
static void pcm_block(const int16_t *mic,int16_t *spk,void *ctx)
{
 (void)mic;(void)ctx;
 taskENTER_CRITICAL();
 if(!pcm_primed && pcm_head-pcm_tail>=9)pcm_primed=true;
 if(pcm_primed && pcm_head!=pcm_tail) {memcpy(spk,audio_pcm[pcm_tail%PCM_QUEUE],320);pcm_tail++;}
 else {memset(spk,0,320);if(pcm_head==pcm_tail)pcm_primed=false;}
 taskEXIT_CRITICAL();
}
static void reset_decoder(uint32_t gen)
{
 worker_generation=gen;selected=requested_mapping<8?requested_mapping:-1;
 for(unsigned i=0;i<8;i++)p25_rx_init(&candidates[i],requested_nac,2);
 dm1701_imbe_init_arm(codec_state);
 taskENTER_CRITICAL();pcm_head=pcm_tail=0;pcm_primed=false;taskEXIT_CRITICAL();
}
static uint8_t dibit(const uint8_t *raw,unsigned i,unsigned map)
{
 unsigned a=i*2,b=a+1;
 unsigned lsb=(map>>2)&1,swap=(map>>1)&1;
 unsigned x=(raw[a>>3]>>(lsb?(a&7):(7-(a&7))))&1;
 unsigned y=(raw[b>>3]>>(lsb?(b&7):(7-(b&7))))&1;
 return (uint8_t)((swap?(x|(y<<1)):((x<<1)|y))^((map&1)?2:0));
}
static void decode_voice(void)
{
 if(!frame.metadata_valid || !frame.clear_voice)return;
 if(frame.nid.duid!=P25_DUID_LDU1 && frame.nid.duid!=P25_DUID_LDU2)return;
 uint32_t start=hal_micros();
 for(unsigned n=0;n<9;n++) {
  int16_t pcm[160];
  if(frame.voice_corrected_bits[n]>9 || dm1701_imbe_decode_arm(codec_state,frame.imbe[n],pcm)<0)
   memset(pcm,0,sizeof pcm);
  taskENTER_CRITICAL();
  if(worker_generation!=generation) {taskEXIT_CRITICAL();return;}
  if(pcm_head-pcm_tail<PCM_QUEUE) {
   memcpy(audio_pcm[pcm_head%PCM_QUEUE],pcm,320);pcm_head++;info.audio_frames++;
  } else info.overruns++;
  taskEXIT_CRITICAL();
 }
 info.decode_us=hal_micros()-start;
}
static void process_raw(const raw_block *input)
{
  raw_block block=*input;
  if(block.gen!=generation)return;
  if(worker_generation!=block.gen)reset_decoder(block.gen);
  for(unsigned j=0;j<144;j++) {
   if(block.gen!=generation)break;
   unsigned lo=selected<0?0:(unsigned)selected,hi=selected<0?8:lo+1;
   for(unsigned map=lo;map<hi;map++) {
    p25_rx *rx=&candidates[map];
    if(p25_rx_push_dibit(rx,dibit(block.raw,j,map))!=1)continue;
    if(p25_decode_frame(rx->frame,p25_frame_bytes(rx->nid.duid),&frame)<0 || !frame.metadata_valid)continue;
    if(selected<0) {
     if(frame.nid.corrected_bits>4 || !frame.clear_voice)continue;
     selected=(int)map;info.mapping=(uint8_t)map;info.locked=1;
    }
    info.locked=1;info.mapping=(uint8_t)selected;last_frame_ms=hal_millis();
    info.frames++;info.nac=frame.nid.nac;
    if(frame.nid.duid==P25_DUID_HDU || frame.nid.duid==P25_DUID_LDU1)info.talkgroup=frame.talkgroup;
    if(frame.nid.duid==P25_DUID_LDU1)info.source_id=frame.source_id;
    decode_voice();
   }
  }
  info.bad_nids=selected>=0?candidates[selected].bad_nids:0;
}
static void decode_task(void *unused)
{
 (void)unused;
 raw_block block;
 for(;;)if(xQueueReceive(raw_queue,&block,portMAX_DELAY)==pdTRUE)process_raw(&block);
}

void studio_p25_leave(void)
{
 if(!active)return;
 if(info.locked && (uint32_t)(hal_millis()-last_frame_ms)>1800u) {
  generation++;info.locked=0;info.mapping=255;
 }
 active=false;generation++;
 wr(0x40,0);wr(0x41,0);wr(0x81,0);
 for(unsigned i=0;i<9;i++)wr(regs[i],(regs[i]==0x40||regs[i]==0x41)?(saved[i]&0x7f):saved[i]);
 if(stream_on && board.audio) {board.audio->stop();board.audio->speaker_pcm(false);}
 stream_on=false;info.enabled=0;info.locked=0;
 taskENTER_CRITICAL();pcm_head=pcm_tail=0;taskEXIT_CRITICAL();
}
static bool start(const radio_view_t *v)
{
 if(!board.audio || !board.audio->start || !board.audio->speaker_pcm || !board.audio_tap || !board.audio_tap->modem_ram)return false;
 if(!worker) {
  if(dm1701_imbe_arm_state_bytes()>sizeof(codec_state))return false;
  raw_queue=xQueueCreate(RAW_QUEUE,sizeof(raw_block));
  if(!raw_queue || xTaskCreate(decode_task,"p25",2048,NULL,3,&worker)!=pdPASS)return false;
 }
 for(unsigned i=0;i<9;i++)if(!reg(regs[i],&saved[i],false))return false;
 active=true; /* A later failure must still restore the complete snapshot. */
 /* Preserve this board's actual IF word (normally450kHz), I/Q orientation,
  * and trim. Select IF RX continuous raw physical mode, no transmitter. */
 if(!wr(0x40,0)||!wr(0x41,0)||!wr(0x81,0)||!wr(0x01,(uint8_t)(saved[0]&0xf0))||!wr(0x10,0x02)||
    !wr(0x5f,0)||!wr(0x83,0xff)||!wr(0x81,1)||!wr(0x40,0x40)||!wr(0x41,0x41)||
    !wr(0x22,0x06)||!wr(0xe0,0xc9)||!wr(0xe2,saved[8]|2))return false;
 generation++;worker_generation=0;selected=-1;tuned_hz=v->ch.rx_hz;
 memset(&info,0,sizeof info);info.enabled=1;info.mapping=255;info.nac=requested_nac;info.scan_mode=requested_scan_mode;
 board.radio->audio(false);
 board.audio->speaker_pcm(true);
 stream_on=board.audio->start(pcm_block,NULL);
 if(!stream_on) {info.fault=2;return false;}
 active=true;return true;
}
void studio_p25_poll(const radio_view_t *v)
{
 receiver_hz=v->ch.rx_hz;
 if(!settings_loaded) {
  settings_t *st=settings_begin();
  if(st->studio_p25_hz && st->studio_p25_hz==v->ch.rx_hz) {
   requested=st->studio_p25_enable==1;requested_nac=st->studio_p25_nac;
   requested_mapping=st->studio_p25_mapping;change=1;tuned_hz=v->ch.rx_hz;
  }
  settings_end(hal_millis());settings_loaded=true;
 }
 if(requested_hz) {
  if(v->ch.rx_hz!=requested_hz || v->ch.mode!=RADIO_MODE_FM)return;
  studio_p25_leave();tuned_hz=0;requested_hz=0;change=1;
 }
 if(v->ch.mode!=RADIO_MODE_FM) {studio_p25_leave();requested=0;change=0;return;}
 if(requested && !active)change=1;
 bool named=v->ch.mode==RADIO_MODE_FM && !strncmp(v->ch.name,"P25",3);
 if(tuned_hz && tuned_hz!=v->ch.rx_hz) {studio_p25_leave();requested=named;change=1;tuned_hz=0;}
 if(!tuned_hz && named && !change) {requested=1;change=1;}
 if(change) {
  change=0;
  studio_p25_leave();
  if(requested && v->ch.mode==RADIO_MODE_FM && v->state!=RS_TX && !v->hotspot) {
   if(!start(v)) {info.fault=1;studio_p25_leave();requested=0;}
  }
  settings_t *st=settings_begin();st->studio_p25_hz=v->ch.rx_hz;
  st->studio_p25_nac=requested_nac;st->studio_p25_enable=requested;
  st->studio_p25_mapping=requested_mapping;settings_end(hal_millis());
 }
 if(!active)return;
 if(v->ch.mode!=RADIO_MODE_FM || v->state==RS_TX || v->hotspot) {studio_p25_leave();requested=0;return;}
 uint8_t flags=0;
 if(!reg(0x82,&flags,false)) {info.fault=3;studio_p25_leave();requested=0;return;}
 if(flags&1) {
  raw_block block={.gen=generation};
  if(!board.audio_tap->modem_ram(2,0x30,block.raw,36,false)||!wr(0x83,flags)) {info.fault=3;studio_p25_leave();requested=0;return;}
  info.blocks++;
  if(xQueueSend(raw_queue,&block,0)!=pdTRUE) {info.overruns++;generation++;}
 }
}
static uint32_t le32(const uint8_t *p) {return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
__attribute__((noinline)) size_t studio_p25_command(const uint8_t *req,uint16_t len,uint8_t *out,size_t cap)
{
 if(!cap)return 0;
 if(!len) {out[0]=DL_ST_BAD_ARG;return 1;}
 if(req[0]==1) {
  if(len!=9 && len!=10) {out[0]=DL_ST_BAD_ARG;return 1;}
  uint32_t hz=le32(req+1);uint16_t nac=(uint16_t)(req[5]|req[6]<<8);
  uint8_t scan=len==10?req[9]:2;
  if(!((hz>=136000000&&hz<=174000000)||(hz>=400000000&&hz<=480000000))||
     (nac>0xfff&&nac!=0xffff)||req[7]>1||(req[8]>7&&req[8]!=255)||scan>2) {out[0]=DL_ST_BAD_ARG;return 1;}
  requested_scan_mode=scan;
  requested_nac=scan==2?0xffff:nac;requested_mapping=req[8];requested=req[7];requested_hz=hz;change=1;
  if(scan==2) {
   /* Use the active zone's channels as the scan set.  Each P25 channel is
    * marked RX-only by the CPS, and the decoder itself accepts every NAC/TG. */
   radio_req_scan(RSCAN_ZONE);radio_req_mode(RADIO_MODE_FM);
  } else {
   radio_req_scan(RSCAN_STOP);radio_req_vfo(true);radio_req_mode(RADIO_MODE_FM);radio_req_vfo_set(hz);
  }
 } else if(req[0]!=0) {out[0]=DL_ST_BAD_ARG;return 1;}
 studio_p25_view_t v;studio_p25_view(&v);
 out[0]=DL_ST_OK;
 return 1+dl_fmt((char*)out+1,cap-1,"protocol=dm1701-p25/1\nboard=DM-1701\nenabled=%u\nrx_hz=%lu\nnac=%04X\nscan_mode=%u\nmapping=%u\nlocked=%u\nfault=%u\nraw_blocks=%lu\nframes=%lu\naudio_frames=%lu\noverruns=%lu\n",(unsigned)v.enabled,(unsigned long)receiver_hz,(unsigned)requested_nac,(unsigned)v.scan_mode,(unsigned)v.mapping,(unsigned)v.locked,(unsigned)v.fault,(unsigned long)v.blocks,(unsigned long)v.frames,(unsigned long)v.audio_frames,(unsigned long)v.overruns);
}
