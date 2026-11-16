/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright (c) 2026 DM-1701 Studio contributors */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "studio_home.h"
#include "p25/studio_p25.h"

static studio_p25_view_t receiver;
uint32_t ui_strip_draws, ui_hint_draws;
void studio_p25_view(studio_p25_view_t *v) { *v = receiver; }
void ui_draw_banner(const ui_state_t *s) { (void)s; }
void ui_draw_hint(const char *s, bool toast) { (void)s; (void)toast; }
void gfx_fit_trace(const char *src, const char *out) { (void)src; (void)out; }
void gfx_draw_trace(gfx_trace_kind_t kind, int x, int y, int w, int h, const int clip[4], const char *s)
{
	(void)clip; (void)s;
	if (kind == GFX_TRACE_TEXT) {
		assert(x >= 0 && y >= 0);
		assert(x + w <= gfx_width());
		assert(y + h <= gfx_height());
	}
}

static void save_ppm(const char *path)
{
	FILE *out = fopen(path, "wb");
	assert(out != NULL);
	assert(fprintf(out, "P6\n160 120\n255\n") > 0);
	for (int y = 0; y < 120; y++) {
		uint8_t row[320];
		gfx_read_rgb565((uint32_t)y * 320u, row, sizeof row);
		for (unsigned x = 0; x < 160; x++) {
			uint16_t pixel = (uint16_t)(row[x*2] | (uint16_t)row[x*2+1] << 8);
			uint8_t rgb[3] = {(uint8_t)(((pixel >> 11) & 31) * 255 / 31),
				(uint8_t)(((pixel >> 5) & 63) * 255 / 63),
				(uint8_t)((pixel & 31) * 255 / 31)};
			assert(fwrite(rgb, 1, sizeof rgb, out) == sizeof rgb);
		}
	}
	assert(fclose(out) == 0);
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	hal_display_t display = {.width=160, .height=120, .bpp=4, .inset_left=5, .inset_right=5};
	assert(gfx_init(&display));
	radio_view_t v = {0};
	ui_state_t s = {0};
	s.battery_pct = 84;
	strcpy(v.zone_name, "PARKER COUNTY");
	strcpy(v.ch.name, "LOCAL P25");
	v.ch.rx_hz = v.ch.tx_hz = 443250000;
	v.ch.rx_only = true;
	v.rssi_dbm = -75;
	receiver.enabled = 1;
	receiver.nac = 0x293;
	receiver.talkgroup = 123;
	receiver.source_id = 123456;
	receiver.locked = 1;
	assert(studio_home_draw(&v, &s));
	save_ppm(argv[1]);

	/* Every mode and extreme field length must fit the DM-1701 safe area. */
	strcpy(v.zone_name, "1234567890123456");
	strcpy(v.ch.name, "1234567890123456");
	v.ch.rx_hz = 174999990;
	receiver.talkgroup = 65535;
	receiver.source_id = 16777215;
	for (unsigned p25 = 0; p25 < 2; p25++)
	for (unsigned mode = 0; mode < 2; mode++)
	for (unsigned state = 0; state < 4; state++) {
		receiver.enabled = p25;
		receiver.fault = state == 3;
		receiver.locked = state == 1;
		v.ch.mode = mode;
		v.state = state;
#if CONFIG_DMR
		v.dmr.target_id = 16777215;
		v.dmr.state = RDMR_RX;
		v.dmr.call.src = 16777215;
#endif
		assert(studio_home_draw(&v, &s));
	}
	assert(ui_strip_draws == 17 && ui_hint_draws == 17);
	puts("PASS original home renderer: FM/DMR/P25 state and maximum names fit 150x120 safe viewport");
	return 0;
}
