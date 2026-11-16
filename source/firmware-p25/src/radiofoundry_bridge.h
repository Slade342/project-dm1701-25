/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef DM1701_RADIOFOUNDRY_BRIDGE_H
#define DM1701_RADIOFOUNDRY_BRIDGE_H
#include "dm1701_rx_probe.h"
#include "modem/hrc_common/hrc.h"
/* Register bridge for the pinned RadioFoundry API. Board code still must claim
 * modem ownership, block normal PTT/channel changes, leave the PA disabled,
 * serialize the SPI bus and redirect only SYS EXTI1 to dm1701_probe_irq().
 * This bridge supplies none of those board scheduling/ownership decisions. */
typedef struct {
    hrc_t *modem;
    void *board_ctx;
    int (*board_rx_safe)(void *);
    uint32_t (*board_micros)(void *);
} dm1701_radiofoundry_bridge;
/* Does not touch hardware. Rejects missing callbacks and non-C6000 cfg pages. */
int dm1701_radiofoundry_io(dm1701_radiofoundry_bridge *,dm1701_probe_io *);
#endif
