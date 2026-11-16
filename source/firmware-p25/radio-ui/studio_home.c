/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright (c) 2026 DM-1701 Studio contributors
 * Original compact professional-radio home display. No manufacturer graphics,
 * trademarks, fonts, or screen assets are embedded. */
#include "studio_home.h"
#include "fmt.h"
#include "p25/studio_p25.h"

#define HOME_BG RGB565(232, 238, 244)
#define HOME_INK RGB565(15, 28, 45)
#define HOME_DIM RGB565(65, 82, 99)
#define HOME_BLUE RGB565(0, 47, 87)
#define HOME_WHITE RGB565(255, 255, 255)
#define HOME_GREEN RGB565(0, 98, 64)
#define HOME_RED RGB565(190, 24, 28)
#define HOME_LINE RGB565(168, 184, 198)

static void centered(const font_t *font, int y, const char *text, color_t color)
{
	char fit[48];
	gfx_text_fit(font, text, gfx_width() - 8, fit, sizeof fit);
	gfx_text(font, (gfx_width() - gfx_text_width(font, fit)) / 2, y, fit, color);
}

static void hex3(sbuf_t *b, uint16_t number)
{
	static const char digits[] = "0123456789ABCDEF";
	for (int shift = 8; shift >= 0; shift -= 4)
		sb_chr(b, digits[(number >> shift) & 15]);
}

static const char *mode_name(const radio_view_t *v, bool p25)
{
	if (p25)
		return "P25";
	return v->ch.mode == RADIO_MODE_DMR ? "DMR" : "FM";
}

static void frequency(char *out, size_t cap, const radio_view_t *v, const ui_state_t *s)
{
	sbuf_t b;
	sb_init(&b, out, cap);
	if (s->entry) {
		for (unsigned i = 0; i < UI_ENTRY_MAX; i++) {
			if (i == UI_ENTRY_MHZ)
				sb_chr(&b, '.');
			sb_chr(&b, i < s->entry_len ? s->entry_digits[i] : '_');
		}
	} else {
		sb_freq(&b, v->state == RS_TX ? v->ch.tx_hz : v->ch.rx_hz);
	}
}

bool studio_home_draw(const radio_view_t *v, const ui_state_t *s)
{
	int w = gfx_width(), h = gfx_height();
	if (w < 140 || h < 118)
		return false;
	studio_p25_view_t p = {0};
	studio_p25_view(&p);
	bool p25 = p.enabled != 0;
	bool tx = !p25 && v->state == RS_TX;
	bool rx = p25 ? p.locked != 0 : v->state == RS_RX;
	color_t state_color = tx ? HOME_RED : rx ? HOME_GREEN : HOME_BLUE;
	char text[48];
	sbuf_t b;

	gfx_clear(HOME_BG);
	/* A fourteen-pixel status band, with explicit state words beside the icons. */
	gfx_fill(0, 0, w, 14, HOME_BLUE);
	int bars = (v->rssi_dbm + 125) / 10;
	if (bars < 0) bars = 0;
	if (bars > 5) bars = 5;
	gfx_icon_bars(3, 2, 18, 10, 5, (uint8_t)bars, HOME_WHITE, HOME_DIM);
	gfx_text(&font_5x8, 26, 3, mode_name(v, p25), HOME_WHITE);
	gfx_text(&font_5x8, 49, 3, tx ? "TX" : rx ? "RX" : "IDLE", HOME_WHITE);
	if (s->scanning || v->scan)
		gfx_text(&font_5x8, 78, 3, "SCAN", HOME_WHITE);
	else if (s->locked)
		gfx_text(&font_5x8, 78, 3, "LOCK", HOME_WHITE);
	else if (p25)
		gfx_text(&font_5x8, 78, 3, "RX ONLY", HOME_WHITE);
	if (!s->no_battery)
		gfx_icon_battery(w - 21, 3, 17, 8, s->battery_pct, HOME_WHITE, HOME_WHITE);
	ui_strip_draws++;

	sb_init(&b, text, sizeof text);
	sb_str(&b, v->vfo ? "VFO" : v->zone_name[0] ? v->zone_name : "ALL CHANNELS");
	centered(&font_5x8, 18, text, HOME_DIM);
	centered(&font_8x16, 29, v->ch.name[0] ? v->ch.name : "SELECT CHANNEL", HOME_INK);

	frequency(text, sizeof text, v, s);
	const font_t *frequency_font = gfx_text_width(&font_12x24, text) <= w - 8 ? &font_12x24 : &font_8x16;
	centered(frequency_font, 48, text, state_color);
	gfx_hline(6, 74, w - 12, HOME_LINE);

	sb_init(&b, text, sizeof text);
	if (p25) {
		sb_str(&b, "NAC ");
		if (p.nac <= 0xFFFu) hex3(&b, p.nac); else sb_str(&b, "ANY");
		sb_str(&b, "   TG ");
		sb_u32(&b, p.talkgroup, 1);
	} else if (v->ch.mode == RADIO_MODE_DMR) {
#if CONFIG_DMR
		sb_str(&b, "TG "); sb_u32(&b, v->dmr.target_id, 1);
		sb_str(&b, "   TS"); sb_u32(&b, v->ch.timeslot, 1);
		sb_str(&b, " C"); sb_u32(&b, v->ch.color_code, 1);
#endif
	} else {
		sb_str(&b, v->ch.bw == RADIO_BW_25K ? "WIDE" : "NARROW");
		sb_str(&b, v->ch.rx_only ? "   RX ONLY" : "   ANALOG FM");
	}
	centered(&font_5x8, 79, text, HOME_INK);

	sb_init(&b, text, sizeof text);
	if (p25) {
		if (p.fault) sb_str(&b, "MODEM ERROR");
		else if (p.locked) {
			sb_str(&b, "RID "); sb_u32(&b, p.source_id, 1);
			sb_str(&b, "  RECEIVING");
		} else sb_str(&b, "SEARCHING - EXPERIMENTAL");
	} else if (v->state == RS_TX_DENIED) {
		sb_str(&b, "TRANSMIT BLOCKED");
	} else {
#if CONFIG_DMR
		if (v->ch.mode == RADIO_MODE_DMR && v->dmr.state == RDMR_RX) {
			sb_str(&b, "RID "); sb_u32(&b, v->dmr.call.src, 1);
		} else
#endif
			sb_str(&b, tx ? "TRANSMITTING" : rx ? "RECEIVING" : "STANDBY");
	}
	centered(&font_5x8, 92, text, p.fault || v->state == RS_TX_DENIED ? HOME_RED : HOME_DIM);

	/* Soft labels follow the actual physical functions: OK, hold #, and *. */
	int by = h - 14, third = w / 3;
	gfx_fill(0, by, w, 14, HOME_BLUE);
	gfx_vline(third, by + 2, 10, HOME_LINE);
	gfx_vline(third * 2, by + 2, 10, HOME_LINE);
	gfx_text(&font_5x8, 6, by + 3, "OK MENU", HOME_WHITE);
	gfx_text(&font_5x8, third + 6, by + 3, "HOLD #", HOME_WHITE);
	gfx_text(&font_5x8, third * 2 + 6, by + 3, "* QUICK", HOME_WHITE);
	ui_hint_draws++;
	ui_draw_banner(s);
	if (s->toast != NULL)
		ui_draw_hint(s->toast, true);
	return true;
}
