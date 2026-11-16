/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef DM1701_RX_PROBE_H
#define DM1701_RX_PROBE_H
#include <stdint.h>
#include <stddef.h>
#include <stdatomic.h>
/* This is an experimental C6000 capture component, NOT a board driver or image.
 * Its owner must serialize begin/end with board modem operations and implement
 * rx_safe(): PTT locked out, PA disabled, RF routed to receive. No TX callbacks.
 * It snapshots/restores the board's modem settings and calibration context;
 * the documented physical test temporarily selects its 455-kHz IF. Default
 * build refuses access.
 */
#ifndef DM1701_EXPERIMENTAL_RX
#define DM1701_EXPERIMENTAL_RX 0
#endif
enum { DM1701_RX_RING=16, DM1701_PROBE_DISABLED=-2, DM1701_PROBE_ERROR=-1 };
typedef struct {
    void *ctx;
    int (*rx_safe)(void *);
    int (*read)(void *,uint8_t page,uint16_t address,uint8_t *out,size_t n);
    int (*write)(void *,uint8_t page,uint16_t address,const uint8_t *data,size_t n);
    uint32_t (*micros)(void *);
} dm1701_probe_io;
typedef struct {
    uint32_t sequence, micros;
    uint8_t irq_flags, kind, ram[36];
} dm1701_rx_record;
typedef struct {
    dm1701_probe_io io;
    /* The documented HRC6000 physical BER test touches these nine system
     * registers.  No page-1 sync register is involved: the previous probe
     * accidentally wrote page-1 address 0x47, which is not a sync address. */
    uint8_t saved[9];
    uint8_t active,snapshot_valid,fault;
    uint32_t sequence,dropped;
    atomic_uint head,tail;
    dm1701_rx_record ring[DM1701_RX_RING];
} dm1701_rx_probe;
/* Both the compile gate and explicit acknowledgement are required. */
int dm1701_probe_begin(dm1701_rx_probe *,const dm1701_probe_io *,int acknowledge_unverified_hardware);
/* Called only on C6000 SYS IRQ, with exclusive access to its SPI interface. */
int dm1701_probe_irq(dm1701_rx_probe *);
int dm1701_probe_pop(dm1701_rx_probe *,dm1701_rx_record *);
/* Restores saved masks/mode/IF, always masks off TX enables. */
int dm1701_probe_end(dm1701_rx_probe *);
#endif
