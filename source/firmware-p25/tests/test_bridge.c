/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "radiofoundry_bridge.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned reads,writes;
bool hrc_read_burst(hrc_t *dev,uint8_t page,uint8_t reg,uint8_t *data,uint16_t n)
{ (void)dev;(void)page;(void)reg;reads++;memset(data,0,n);return true; }
bool hrc_write_burst(hrc_t *dev,uint8_t page,uint8_t reg,const uint8_t *data,uint16_t n)
{ (void)dev;(void)page;(void)reg;(void)data;(void)n;writes++;return true; }
static int safe(void *ctx) { return *(int *)ctx; }
static uint32_t micros(void *ctx) { (void)ctx;return 99; }
int main(void)
{
    int ok=1;
    hrc_chip_t chip={0};chip.cfg_page=4;
    hrc_t modem={0};modem.chip=&chip;
    dm1701_radiofoundry_bridge bridge={&modem,&ok,safe,micros};
    dm1701_probe_io io;
    assert(dm1701_radiofoundry_io(&bridge,&io));
    assert(!reads && !writes && io.rx_safe(io.ctx) && io.micros(io.ctx)==99);
    uint8_t buf[36]={0};
    assert(io.read(io.ctx,2,0x30,buf,36) && reads==1);
    assert(io.write(io.ctx,4,0x40,buf,1) && writes==1);
    assert(!io.write(io.ctx,2,0x30,buf,36));
    buf[0]=0x80;assert(!io.write(io.ctx,4,0x40,buf,1));
    assert(!io.read(io.ctx,4,256,buf,1));
    assert(!io.read(io.ctx,4,255,buf,2));
    chip.cfg_page=0;assert(!dm1701_radiofoundry_io(&bridge,&io));
    puts("PASS pinned RadioFoundry bridge: no initialization I/O, actual burst API, page/address limits, TX rejection, chip-page guard");
    return 0;
}
