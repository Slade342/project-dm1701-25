/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "dm1701_rx_probe.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct { uint8_t page[5][512];unsigned calls,fail_call,writes;int safe; } fake;
static int rd(void *ctx,uint8_t p,uint16_t r,uint8_t *out,size_t n)
{ fake *f=ctx;f->calls++;if(f->calls==f->fail_call)return 0;assert(p<5 && r+n<=512);memcpy(out,&f->page[p][r],n);return 1; }
static int wr(void *ctx,uint8_t p,uint16_t r,const uint8_t *in,size_t n)
{
    fake *f=ctx;f->calls++;if(f->calls==f->fail_call)return 0;
    assert(p==1 || p==4);assert(r+n<=512);f->writes++;
    if(p==4 && (r==0x40 || r==0x41))assert(!(in[0]&0x80));
    if(p==4 && r==0x83) { assert(in[0]&1);f->page[4][0x82]&=(uint8_t)~in[0]; }
    else memcpy(&f->page[p][r],in,n);
    return 1;
}
static int safe(void *ctx) { return ((fake *)ctx)->safe; }
static uint32_t micros(void *ctx) { (void)ctx;return 123456; }
static void init(fake *f,dm1701_probe_io *io)
{
    memset(f,0,sizeof *f);f->safe=1;
    f->page[4][0x01]=0xb0;f->page[4][0x07]=0x0b;f->page[4][0x08]=0xb8;
    f->page[4][0x09]=0x00;f->page[4][0x10]=0x6e;f->page[4][0x40]=0xc3;
    f->page[4][0x41]=0x80;f->page[4][0x5f]=0xf0;f->page[4][0x81]=0x19;
    *io=(dm1701_probe_io){f,safe,rd,wr,micros};
}
int main(void)
{
    fake f;dm1701_probe_io io;dm1701_rx_probe p;dm1701_rx_record rec;
    init(&f,&io);
    assert(dm1701_probe_begin(&p,&io,0)<0 && !f.writes);
    f.safe=0;assert(dm1701_probe_begin(&p,&io,1)<0 && !f.writes);
    init(&f,&io);assert(dm1701_probe_begin(&p,&io,1)==1);
    assert(f.page[4][0x01]==0xb0 && f.page[4][0x07]==0x0b && f.page[4][0x08]==0xd9 &&
           f.page[4][0x09]==0x54 && f.page[4][0x10]==2 && f.page[4][0x40]==0x40 &&
           f.page[4][0x41]==0x41 && f.page[4][0x81]==1);
    assert(dm1701_probe_irq(&p)==0);
    for(unsigned i=0;i<DM1701_RX_RING+1;i++) {
        f.page[4][0x82]=0x09;f.page[4][0x51]=2;
        memset(&f.page[2][0x30],(int)i,36);
        assert(dm1701_probe_irq(&p)==(i<DM1701_RX_RING?1:0));
        assert(f.page[4][0x82]==0); /* write back the complete physical IRQ flags */
    }
    assert(p.dropped==1 && p.sequence==17);
    assert(dm1701_probe_pop(&p,&rec)==1 && rec.sequence==0 && rec.micros==123456 && rec.kind==2);
    f.page[4][0x82]=1;assert(dm1701_probe_irq(&p)==1);
    for(unsigned i=1;i<DM1701_RX_RING;i++)assert(dm1701_probe_pop(&p,&rec)==1 && rec.sequence==i);
    assert(dm1701_probe_pop(&p,&rec)==1 && rec.sequence==17);
    assert(dm1701_probe_pop(&p,&rec)==0);
    assert(dm1701_probe_end(&p)==1);
    assert(f.page[4][0x01]==0xb0 && f.page[4][0x07]==0x0b && f.page[4][0x08]==0xb8 &&
           f.page[4][0x09]==0x00 && f.page[4][0x10]==0x6e && f.page[4][0x40]==0x43 &&
           f.page[4][0x41]==0 && f.page[4][0x5f]==0xf0 && f.page[4][0x81]==0x19);
    /* Inject a failure at each snapshot/setup bus operation. Setup failures
     * attempt rollback; no recorded write ever contains a TX enable. */
    for(unsigned fail=1;fail<=22;fail++) {
        init(&f,&io);f.fail_call=fail;
        assert(dm1701_probe_begin(&p,&io,1)<0);
        assert(!p.active);
    }
    init(&f,&io);assert(dm1701_probe_begin(&p,&io,1)==1);
    f.safe=0;assert(dm1701_probe_irq(&p)<0 && !p.active && p.fault);
    init(&f,&io);assert(dm1701_probe_begin(&p,&io,1)==1);
    f.fail_call=f.calls+1;assert(dm1701_probe_irq(&p)<0 && !p.active && p.fault);
    puts("PASS C6000 probe: gate, RX-only writes, rollback, IRQ acknowledgement, sequence gaps, overflow, RF ownership loss, bus fault");
    return 0;
}
