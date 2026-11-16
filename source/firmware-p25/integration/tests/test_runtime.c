/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <assert.h>
#include <stdio.h>
#include "../studio_p25.c"

static uint8_t chip[256],raw[36];
static raw_block posted;
static unsigned timestamp,plays,outputs,fail_reg;
static settings_t settings;
static bool modem_reg(uint8_t page,uint8_t r,uint8_t *v,bool write)
{
 assert(page==4);
 if(fail_reg==r)return false;
 if(write) {chip[r]=*v;if(r==0x83)chip[0x82]=0;}
 else *v=chip[r];
 return true;
}
static bool modem_ram(uint8_t p,uint16_t address,uint8_t *out,uint16_t len,bool write)
{assert(p==2 && address==0x30 && len==36 && !write);memcpy(out,raw,36);return true;}
static bool audio_start(audio_block_cb_t fn,void *ctx) {(void)fn;(void)ctx;plays++;return true;}
static void audio_stop(void) {}
static void audio_switch(bool on) {(void)on;}
static const hal_audio_t audio={.start=audio_start,.stop=audio_stop,.speaker_pcm=audio_switch};
static const hal_audio_tap_t tap={.modem_reg=modem_reg,.modem_ram=modem_ram};
static const hal_radio_t rf={.audio=audio_switch};
const board_t board={.audio=&audio,.audio_tap=&tap,.radio=&rf};
uint32_t hal_micros(void) {return timestamp++;}
uint32_t hal_millis(void) {return timestamp/1000;}
settings_t *settings_begin(void) {return &settings;}
void settings_end(uint32_t t) {(void)t;}
void radio_req_scan(uint8_t mode) {(void)mode;}
void radio_req_vfo(bool on) {(void)on;}
void radio_req_mode(uint8_t mode) {(void)mode;}
void radio_req_vfo_set(uint32_t hz) {(void)hz;}
QueueHandle_t xQueueCreate(unsigned count,unsigned bytes) {assert(count==16 && bytes==sizeof(raw_block));return (void*)1;}
BaseType_t xTaskCreate(void (*fn)(void*),const char *name,unsigned stack,void *ctx,unsigned prio,TaskHandle_t *task)
{(void)fn;(void)name;(void)stack;(void)ctx;(void)prio;*task=(void*)1;return pdPASS;}
BaseType_t xQueueReceive(QueueHandle_t q,void *out,uint32_t timeout) {(void)q;(void)out;(void)timeout;return 0;}
BaseType_t xQueueSend(QueueHandle_t q,const void *in,uint32_t timeout) {(void)q;(void)timeout;memcpy(&posted,in,sizeof posted);return pdTRUE;}

int main(int argc,char **argv)
{
 assert(argc==2);
 FILE *file=fopen(argv[1],"rb");assert(file);
 radio_view_t v={0};v.ch.mode=RADIO_MODE_FM;v.ch.rx_hz=443250000;
 requested=1;change=1;settings_loaded=true;fail_reg=999;
 studio_p25_poll(&v);assert(active && stream_on && plays==1);
 unsigned blocks=0;
 while(1) {
  memset(raw,0,sizeof raw);size_t count=fread(raw,1,36,file);if(!count)break;
  chip[0x82]=1;studio_p25_poll(&v);process_raw(&posted);
  for(unsigned i=0;i<(blocks%2?2u:1u);i++) {
   int16_t pcm[160];pcm_block(NULL,pcm,NULL);
   for(unsigned j=0;j<160;j++)if(pcm[j]) {outputs++;break;}
  }
  blocks++;
 }
 fclose(file);
 assert(info.frames>2 && info.audio_frames>0 && outputs>0 && info.overruns==0);
 assert(info.mapping<8 && info.locked && pcm_head-pcm_tail<=16);
 studio_p25_leave();assert(!active && !stream_on);
 raw_block stale=posted;generation++;uint32_t before=info.frames;process_raw(&stale);assert(info.frames==before);
 requested=1;change=1;fail_reg=0xe0;studio_p25_poll(&v);assert(!active && !requested && info.fault);
 printf("PASS actual voice runtime: %u raw blocks, %lu P25 frames, %lu PCM blocks, mapping %u, stale-block rejection and start rollback\n",blocks,(unsigned long)before,(unsigned long)info.audio_frames,info.mapping);
 return 0;
}
