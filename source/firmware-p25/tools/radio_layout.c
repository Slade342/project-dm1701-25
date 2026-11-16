/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "radio_app.h"
#include <stdio.h>
static int tune(void *p,const radio_channel *c){(void)p;(void)c;return 0;}
static void rect(void *p,int x,int y,int w,int h,uint32_t rgb){(void)p;printf("<rect x='%d' y='%d' width='%d' height='%d' fill='#%06lx'/>\n",x,y,w,h,(unsigned long)rgb);}
static void text(void *p,int x,int y,unsigned size,uint32_t rgb,const char *s){(void)p;printf("<text x='%d' y='%d' font-size='%u' fill='#%06lx'>",x,y,size==2?15u:8u,(unsigned long)rgb);for(;*s;s++){switch(*s){case '&':fputs("&amp;",stdout);break;case '<':fputs("&lt;",stdout);break;case '>':fputs("&gt;",stdout);break;default:putchar(*s);}}puts("</text>");}
int main(void){radio_app a;radio_board b={0};radio_display d={NULL,rect,text};radio_channel c={"P25 SIMPLEX",433450000,433450000,1234567,0x293,9,RADIO_P25,1,1,1,1,1,1};b.tune=tune;if(radio_init(&a,&b,&c,1))return 1;puts("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 120' width='640' height='480' font-family='monospace'>");radio_render(&a,&d);puts("</svg>");return 0;}
