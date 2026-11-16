/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "radio_app.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

static int band(uint32_t hz){return (hz>=136000000u&&hz<=174000000u)||(hz>=400000000u&&hz<=480000000u);}
static void note(radio_app *a,const char *s){snprintf(a->notice,sizeof a->notice,"%s",s);}
int radio_channel_valid(const radio_channel *c){
 return c && c->name[0] && memchr(c->name,0,sizeof c->name) && band(c->rx_hz) && band(c->tx_hz)
 && c->rx_hz%10u==0 && c->tx_hz%10u==0 && c->mode<=RADIO_P25 && c->rx_only<=1 && c->scan<=1
 && c->audio<=1 && c->promiscuous<=1
 && c->nac<=0xfff && c->source_id>0 && c->source_id<=0xffffff && c->talkgroup>0
 && c->color_code<=15 && c->time_slot>=1 && c->time_slot<=2;
}
int radio_init(radio_app *a,const radio_board *b,const radio_channel *c,size_t n){
 size_t i;
 if(!a||!b||!b->tune||!c||!n||n>RADIO_CHANNELS)return -1;
 for(i=0;i<n;i++)if(!radio_channel_valid(&c[i]))return -1;
 memset(a,0,sizeof *a);a->board=*b;a->count=(uint8_t)n;
 memcpy(a->channels,c,n*sizeof *c);
 a->tuned=(uint8_t)(a->board.tune(a->board.ctx,&a->channels[0])==0);
 return a->tuned?0:-1;
}
int radio_fpp_begin(radio_app *a,int add){
 if(!a||a->transmitting||a->editing||(add&&a->count==RADIO_CHANNELS))return -1;
 a->scanning=0;a->editing=1;a->adding=!!add;a->field=0;a->name_pos=0;a->digits_used=0;
 a->edit=a->channels[a->selected];
 if(add){snprintf(a->edit.name,sizeof a->edit.name,"New channel");a->edit.rx_only=1;}
 note(a,"FPP: OK saves");return 0;
}
static int integer(const char *s,unsigned base,uint32_t max,uint32_t *out){
 char *end;unsigned long n;
 if(!s||!*s||*s=='-'||*s=='+')return -1;
 errno=0;n=strtoul(s,&end,(int)base);
 if(errno||*end||n>max)return -1;
 *out=(uint32_t)n;return 0;
}
/* MHz conversion uses integer decimal arithmetic, including an exact 10Hz check. */
static int frequency(const char *s,uint32_t *out){
 uint32_t whole=0,frac=0,scale=100000;unsigned n=0;
 if(!s||!*s)return -1;
 while(*s>='0'&&*s<='9'){if(++n>3)return -1;whole=whole*10u+(uint32_t)(*s++-'0');}
 if(!n)return -1;
 if(*s=='.'){s++;while(*s>='0'&&*s<='9'){if(!scale)return -1;frac+=(uint32_t)(*s++-'0')*scale;scale/=10u;}}
 if(*s)return -1;
 *out=whole*1000000u+frac;return band(*out)&&*out%10u==0?0:-1;
}
int radio_fpp_set(radio_app *a,unsigned f,const char *s){
 uint32_t n;radio_channel c;
 if(!a||!a->editing||!s)return -1;
 c=a->edit;
 if(f==FPP_NAME){if(!*s||strlen(s)>16)return -1;snprintf(c.name,sizeof c.name,"%s",s);}
 else if(f==FPP_RX||f==FPP_TX){if(frequency(s,&n))return -1;if(f==FPP_RX)c.rx_hz=n;else c.tx_hz=n;}
 else {if(integer(s,f==FPP_NAC?16:10,0xffffff,&n))return -1;
 switch(f){
 case FPP_MODE:if(n>2)return -1;c.mode=(uint8_t)n;break;
 case FPP_NAC:if(n>0xfff)return -1;c.nac=(uint16_t)n;break;
 case FPP_TG:if(!n||n>65535)return -1;c.talkgroup=(uint16_t)n;break;
 case FPP_ID:if(!n)return -1;c.source_id=n;break;
 case FPP_CC:if(n>15)return -1;c.color_code=(uint8_t)n;break;
 case FPP_SLOT:if(n<1||n>2)return -1;c.time_slot=(uint8_t)n;break;
 case FPP_SCAN:if(n>1)return -1;c.scan=(uint8_t)n;break;
 case FPP_RXONLY:if(n>1)return -1;c.rx_only=(uint8_t)n;break;
 case FPP_AUDIO:if(n>1)return -1;c.audio=(uint8_t)n;break;
 case FPP_PROMISCUOUS:if(n>1)return -1;c.promiscuous=(uint8_t)n;break;
 default:return -1;
 }}
 a->edit=c;return 0;
}
int radio_fpp_commit(radio_app *a){
 radio_channel old;uint8_t idx,n;
 if(!a||!a->editing||!radio_channel_valid(&a->edit))return -1;
 idx=a->adding?a->count:a->selected;n=a->count;
 old=a->channels[idx];a->channels[idx]=a->edit;
 if(a->adding)a->count++;
 if(!a->board.save||a->board.save(a->board.ctx,a->channels,a->count)){
  a->channels[idx]=old;a->count=n;note(a,"SAVE FAILED");return -1;
 }
 a->selected=idx;a->editing=0;
 a->tuned=(uint8_t)(a->board.tune(a->board.ctx,&a->channels[idx])==0);
 if(!a->tuned){note(a,"TUNE FAILED");return -1;}
 note(a,"CHANNEL SAVED");return 0;
}
static void next_channel(radio_app *a,int direction,int scan){
 unsigned i;uint8_t next=a->selected;
 for(i=0;i<a->count;i++){
  next=(uint8_t)((next+a->count+direction)%a->count);
  if(!scan||a->channels[next].scan||a->promiscuous_scan){
   a->tuned=(uint8_t)(a->board.tune(a->board.ctx,&a->channels[next])==0);
   if(!a->tuned){a->scanning=0;note(a,"TUNE FAILED");return;}
   a->selected=next;return;
  }
 }
 a->scanning=0;note(a,"NO SCAN MEMBERS");
}
void radio_tick(radio_app *a,uint32_t now,int busy){
 if(!a)return;
 a->rf_busy=!!busy;
 if(!a->scanning||a->editing||a->transmitting)return;
 if(busy){a->holding=1;a->deadline=now+1500u;return;}
 if((int32_t)(now-a->deadline)>=0){a->holding=0;next_channel(a,1,1);a->deadline=now+120u;}
}
void radio_digit(radio_app *a,char digit){
 if(!a||!a->editing)return;
 if(a->field==FPP_NAME){if(digit>=32&&digit<=126){a->edit.name[a->name_pos]=digit;
  if(a->name_pos<15)a->name_pos++;
  a->edit.name[a->name_pos]=0;}return;}
 if((digit>='0'&&digit<='9')||digit=='.'||(a->field==FPP_NAC&&((digit>='A'&&digit<='F')||(digit>='a'&&digit<='f')))){
  if(a->digits_used<sizeof a->digits-1){a->digits[a->digits_used++]=digit;a->digits[a->digits_used]=0;}
 }
}
void radio_key(radio_app *a,unsigned key,uint32_t now){
 unsigned i;
 if(!a)return;
 if(key==KEY_PTT_UP){if(a->transmitting&&a->board.tx_end)a->board.tx_end(a->board.ctx);a->transmitting=0;return;}
 if(a->transmitting)return;
 if(a->editing){
  if(key==KEY_BACK){a->editing=0;note(a,"EDIT CANCELED");return;}
  if(key==KEY_OK||key==KEY_NEXT||key==KEY_DOWN||key==KEY_UP){
   if(a->digits_used){if(radio_fpp_set(a,a->field,a->digits)){note(a,"INVALID VALUE");return;}a->digits_used=0;a->digits[0]=0;}
   if(key==KEY_OK){(void)radio_fpp_commit(a);return;}
   a->field=(uint8_t)((a->field+FPP_COUNT+(key==KEY_UP?-1:1))%FPP_COUNT);a->name_pos=0;
  }return;
 }
 if(key==KEY_PTT_DOWN){
  if(!a->tuned){note(a,"TUNE FAILED");return;}
  if(a->channels[a->selected].rx_only){note(a,"RECEIVE ONLY");return;}
  a->scanning=0;
  if(!a->board.tx_begin||a->board.tx_begin(a->board.ctx,&a->channels[a->selected])){note(a,"TX NOT READY");return;}
  a->transmitting=1;return;
 }
 if(key==KEY_MENU){(void)radio_fpp_begin(a,0);return;}
 if(key==KEY_SCAN){
  if(a->scanning){a->scanning=0;a->holding=0;note(a,"SCAN OFF");return;}
  /* Holding the selected channel's PROMISC flag turns scan into a
   * non-affiliate/open receiver experiment. It still never enables TX. */
  if(a->channels[a->selected].promiscuous){
   a->promiscuous_scan=1;a->scanning=1;a->holding=0;a->deadline=now;note(a,"PROMISC SCAN ON");return;
  }
  for(i=0;i<a->count;i++)if(a->channels[i].scan)break;
  if(i==a->count){note(a,"NO SCAN MEMBERS");return;}
  a->promiscuous_scan=0;a->scanning=1;a->holding=0;a->deadline=now;note(a,"SCAN ON");return;
 }
 if(key==KEY_UP||key==KEY_DOWN){a->scanning=0;next_channel(a,key==KEY_UP?1:-1,0);}
}
void radio_render(const radio_app *a,const radio_display *d){
 const radio_channel *c;char text[48];
 static const char *modes[]={"FM","DMR","P25"};
 static const char *fields[]={"NAME","MODE 0FM 1DMR 2P25","RX MHz","TX MHz","NAC hex","TALKGROUP","RADIO ID","COLOR CODE","TIME SLOT","SCAN 0/1","RX ONLY 0/1","AUDIO 0/1","PROMISC 0/1"};
 if(!a||!d||!d->rect||!d->text)return;
 c=a->editing?&a->edit:&a->channels[a->selected];
 d->rect(d->ctx,0,0,160,120,0x101820);d->rect(d->ctx,0,0,160,18,0x243b53);
 snprintf(text,sizeof text,"%s  %s %s",modes[c->mode],a->scanning?(a->promiscuous_scan?"PROMISC":"SCAN"):"DIRECT",a->transmitting?"TX":a->rf_busy?"RX":"STBY");
 d->text(d->ctx,5,12,1,0xffffff,text);
 if(a->editing){
  d->text(d->ctx,5,34,1,0xd6e7f5,"APX-STYLE FPP");
  d->text(d->ctx,5,54,1,0x9fd3ff,fields[a->field]);
  if(a->digits_used)snprintf(text,sizeof text,"%s",a->digits);
  else switch(a->field){
   case FPP_NAME:snprintf(text,sizeof text,"%s",c->name);break;
   case FPP_RX:case FPP_TX:{uint32_t hz=a->field==FPP_RX?c->rx_hz:c->tx_hz;snprintf(text,sizeof text,"%lu.%05lu",(unsigned long)(hz/1000000u),(unsigned long)((hz%1000000u)/10u));break;}
   case FPP_NAC:snprintf(text,sizeof text,"%03X",c->nac);break;
   default:snprintf(text,sizeof text,"Use keypad / next");break;
  }
  d->text(d->ctx,5,76,2,0xffffff,text);
 }else{
  snprintf(text,sizeof text,"ZONE 1  CH %02u",(unsigned)a->selected+1);d->text(d->ctx,5,33,1,0x9fd3ff,text);
  d->text(d->ctx,5,55,2,0xffffff,c->name);
  snprintf(text,sizeof text,"RX %lu.%05lu MHz",(unsigned long)(c->rx_hz/1000000u),(unsigned long)((c->rx_hz%1000000u)/10u));d->text(d->ctx,5,76,1,0xe6f2ff,text);
  snprintf(text,sizeof text,"NAC %03X TG %u %s",c->nac,c->talkgroup,c->promiscuous?"OPEN":"LOCK");d->text(d->ctx,5,92,1,0x9fd3ff,text);
 }
 d->text(d->ctx,5,103,1,0xffd166,a->notice);
 d->rect(d->ctx,0,106,160,14,0x243b53);
 d->text(d->ctx,5,117,1,0xffffff,a->editing?"BACK    NEXT    SAVE":"ZONE    MENU    SCAN");
}
