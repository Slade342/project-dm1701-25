/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Render the actual firmware home renderer on a host display buffer. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "studio_home.h"
#include "p25/studio_p25.h"
uint32_t ui_strip_draws,ui_hint_draws;
void ui_draw_banner(const ui_state_t *s) {(void)s;}
void ui_draw_hint(const char *text,bool warning) {(void)text;(void)warning;}
void studio_p25_view(studio_p25_view_t *v)
{memset(v,0,sizeof *v);v->enabled=1;v->locked=1;v->nac=0x293;v->talkgroup=123;v->source_id=123456;}
static void flush(const void *fb,const uint16_t *palette,uint16_t first,uint16_t last)
{(void)fb;(void)palette;(void)first;(void)last;}
static const hal_display_t display={.width=160,.height=120,.bpp=4,.inset_left=5,.inset_right=5,.flush_indexed=flush};
int main(int argc,char **argv)
{
 assert(argc==2 && gfx_init(&display));
 radio_view_t v={0};ui_state_t s={0};
 strcpy(v.zone_name,"LOCAL");strcpy(v.ch.name,"P25 RECEIVE");v.ch.rx_hz=443250000;
 v.ch.mode=RADIO_MODE_FM;v.ch.rx_only=true;v.rssi_dbm=-80;s.battery_pct=80;
 assert(studio_home_draw(&v,&s));assert(gfx_width()==150 && gfx_height()==120);
 FILE *out=fopen(argv[1],"wb");assert(out);fprintf(out,"P6\n150 120\n255\n");
 for(int y=0;y<120;y++)for(int x=0;x<150;x++) {
  color_t c=gfx_get_pixel(x,y);unsigned char rgb[3]={((c>>11)&31)*255/31,((c>>5)&63)*255/63,(c&31)*255/31};
  assert(fwrite(rgb,1,3,out)==3);
 }
 fclose(out);puts("PASS actual radio home renderer: 160x120 panel / 150x120 safe area");return 0;
}
