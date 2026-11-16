/* SPDX-License-Identifier: GPL-3.0-or-later
 * Register provenance: RadioFoundry hrc6000-registers.md sections 2.2,3.18,
 * 4.1 and 6.4; see PROVENANCE.md. Continuous P25 behavior is unverified.
 * The documented BER-test RX mode is the experiment; no undocumented register
 * values, IF retuning, calibration writes, TX enable, PA key or flash writes.
 */
#include "dm1701_rx_probe.h"
#include "p25_runtime.h"
/* HRC6000-registers.md 6.4 / table 5.6.  The three IF bytes are included
 * because the physical-layer test has its own documented 455-kHz setting. */
static const uint16_t regs[9]={0x01,0x07,0x08,0x09,0x10,0x40,0x41,0x5f,0x81};
static int w(dm1701_rx_probe *p,uint16_t r,uint8_t v)
{ return p->io.write(p->io.ctx,4,r,&v,1); }
int dm1701_probe_end(dm1701_rx_probe *p)
{
    if(!p || !p->snapshot_valid)return 0;
    p->active=0;
    int ok=w(p,0x40,0);
    ok=w(p,0x41,0)&&ok;
    ok=w(p,0x81,0)&&ok;
    for(unsigned i=0;i<9;i++) {
        uint8_t v=p->saved[i];
        if(regs[i]==0x40 || regs[i]==0x41)v&=0x7f; /* NEVER restore TX enables */
        ok=w(p,regs[i],v)&&ok;
    }
    p->snapshot_valid=0;
    return ok?1:DM1701_PROBE_ERROR;
}
int dm1701_probe_begin(dm1701_rx_probe *p,const dm1701_probe_io *io,int acknowledge)
{
#if !DM1701_EXPERIMENTAL_RX
    (void)p;(void)io;(void)acknowledge;
    return DM1701_PROBE_DISABLED;
#else
    if(!p || !io || !acknowledge || !io->rx_safe || !io->read || !io->write || !io->micros || !io->rx_safe(io->ctx))return DM1701_PROBE_ERROR;
    memset(p,0,sizeof *p);
    p->io=*io;
    atomic_init(&p->head,0);atomic_init(&p->tail,0);
    for(unsigned i=0;i<9;i++)if(!io->read(io->ctx,4,regs[i],&p->saved[i],1))return DM1701_PROBE_ERROR;
    p->snapshot_valid=1;
    /* The manual's physical-layer BER test: IF receive (low nibble zero),
     * 455-kHz IF, continuous physical mode, RX test enable.  The mode is
     * receive-only and never asserts a TX-enable bit. */
    uint8_t hw_config=(uint8_t)(p->saved[0]&0xf0u);
    if(!w(p,0x40,0) || !w(p,0x41,0) || !w(p,0x81,0) ||
       !w(p,0x01,hw_config) || !w(p,0x07,0x0b) || !w(p,0x08,0xd9) ||
       !w(p,0x09,0x54) || !w(p,0x10,0x02) || !w(p,0x5f,0) ||
       !w(p,0x83,0xff) || !w(p,0x81,1) || !w(p,0x40,0x40) ||
       !w(p,0x41,0x41)) {
        p->fault=1;dm1701_probe_end(p);return DM1701_PROBE_ERROR;
    }
    p->active=1;
    return 1;
#endif
}
int dm1701_probe_irq(dm1701_rx_probe *p)
{
    if(!p || !p->active)return DM1701_PROBE_ERROR;
    if(!p->io.rx_safe(p->io.ctx)) { p->fault=1;dm1701_probe_end(p);return DM1701_PROBE_ERROR; }
    uint8_t flags;
    if(!p->io.read(p->io.ctx,4,0x82,&flags,1))goto fault;
    if(!(flags&1))return 0;
    dm1701_rx_record r;
    r.sequence=p->sequence++;r.micros=p->io.micros(p->io.ctx);r.irq_flags=flags;
    if(!p->io.read(p->io.ctx,4,0x51,&r.kind,1) || !p->io.read(p->io.ctx,2,0x30,r.ram,36) || !w(p,0x83,flags))goto fault;
    r.kind&=3;
    unsigned head=atomic_load_explicit(&p->head,memory_order_relaxed);
    unsigned tail=atomic_load_explicit(&p->tail,memory_order_acquire);
    if(head-tail>=DM1701_RX_RING) { p->dropped++;return 0; }
    p->ring[head%DM1701_RX_RING]=r;
    atomic_store_explicit(&p->head,head+1,memory_order_release);
    return 1;
fault:
    p->fault=1;dm1701_probe_end(p);return DM1701_PROBE_ERROR;
}
int dm1701_probe_pop(dm1701_rx_probe *p,dm1701_rx_record *out)
{
    if(!p || !out)return DM1701_PROBE_ERROR;
    unsigned tail=atomic_load_explicit(&p->tail,memory_order_relaxed);
    unsigned head=atomic_load_explicit(&p->head,memory_order_acquire);
    if(tail==head)return 0;
    *out=p->ring[tail%DM1701_RX_RING];
    atomic_store_explicit(&p->tail,tail+1,memory_order_release);
    return 1;
}
