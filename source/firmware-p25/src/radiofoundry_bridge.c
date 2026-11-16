/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "radiofoundry_bridge.h"
static int rx_safe(void *ctx)
{
    dm1701_radiofoundry_bridge *b=ctx;
    return b->board_rx_safe(b->board_ctx);
}
static uint32_t micros(void *ctx)
{
    dm1701_radiofoundry_bridge *b=ctx;
    return b->board_micros(b->board_ctx);
}
static int read_regs(void *ctx,uint8_t page,uint16_t address,uint8_t *out,size_t n)
{
    dm1701_radiofoundry_bridge *b=ctx;
    if((page!=1 && page!=2 && page!=4) || address>255 || n>96 || n>(size_t)(256-address))return 0;
    return hrc_read_burst(b->modem,page,(uint8_t)address,out,(uint16_t)n);
}
static int write_regs(void *ctx,uint8_t page,uint16_t address,const uint8_t *data,size_t n)
{
    dm1701_radiofoundry_bridge *b=ctx;
    /* The receive experiment never writes data RAM. */
    if((page!=1 && page!=4) || address>255 || n>96 || n>(size_t)(256-address))return 0;
    if(page==4 && (address==0x40 || address==0x41) && n==1 && (data[0]&0x80))return 0;
    return hrc_write_burst(b->modem,page,(uint8_t)address,data,(uint16_t)n);
}
int dm1701_radiofoundry_io(dm1701_radiofoundry_bridge *b,dm1701_probe_io *out)
{
    if(!b || !out || !b->modem || !b->modem->chip || b->modem->chip->cfg_page!=4 || !b->board_rx_safe || !b->board_micros)return 0;
    *out=(dm1701_probe_io){b,rx_safe,read_regs,write_regs,micros};
    return 1;
}
