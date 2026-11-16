/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright (c) 2026 DM-1701 Studio contributors */
#ifndef STUDIO_HOME_H
#define STUDIO_HOME_H
#include "ui_screens.h"
/* Original professional-radio layout. Uses the board's visible safe area;
 * returns false on a display smaller than this port's 150 x 120 viewport. */
bool studio_home_draw(const radio_view_t *radio, const ui_state_t *ui);
#endif
