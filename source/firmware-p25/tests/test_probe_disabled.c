/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "dm1701_rx_probe.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    assert(dm1701_probe_begin(NULL,NULL,1)==DM1701_PROBE_DISABLED);
    puts("PASS C6000 probe default gate refuses all hardware access");
    return 0;
}
