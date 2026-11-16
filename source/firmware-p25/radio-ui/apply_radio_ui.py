#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 DM-1701 Studio contributors
"""Apply the original Studio home renderer to an isolated RadioFoundry derivative.

This never targets the upstream source checkout. The caller has already copied
the pinned MIT source tree into its derivative build directory.
"""
from pathlib import Path
import shutil


def replace_once(path: Path, before: str, after: str) -> None:
    text = path.read_text(encoding="utf-8")
    if after in text:
        return
    if text.count(before) != 1:
        raise RuntimeError(f"{path}: expected exactly one renderer hook")
    path.write_text(text.replace(before, after), encoding="utf-8")


def apply(tree: Path, overlay_dir: Path | None = None) -> None:
    tree = Path(tree)
    overlay_dir = Path(overlay_dir) if overlay_dir else Path(__file__).resolve().parent
    ui = tree / "core" / "ui"
    if not (ui / "ui_screens.c").is_file():
        raise ValueError("Expected an isolated RadioFoundry derivative source tree")
    for filename in ("studio_home.c", "studio_home.h"):
        shutil.copyfile(overlay_dir / filename, ui / filename)
    replace_once(ui / "ui_screens.c", '#include "ui_screens.h"',
                 '#include "ui_screens.h"\n#include "studio_home.h"')
    replace_once(ui / "ui_screens.c",
                 'void ui_draw_home(const radio_view_t *v, const ui_state_t *s)\n{',
                 'void ui_draw_home(const radio_view_t *v, const ui_state_t *s)\n{\n'
                 '\tif (studio_home_draw(v, s))\n\t\treturn;')
    replace_once(ui / "ui_app.c", '#include "config.h"',
                 '#include "config.h"\n#include "p25/studio_p25.h"')
    # The global long-context handler consumes # before ui_home_key sees it.
    # Keep DMR's target picker and other screens' existing behavior unchanged.
    replace_once(ui / "ui_app.c",
                 '\tif (ev->action == ACT_CONTEXT && ev->gesture == GESTURE_LONG) {\n'
                 '\t\tif (!CONFIG_DMR || view->ch.mode != RADIO_MODE_DMR)',
                 '\tif (ev->action == ACT_CONTEXT && ev->gesture == GESTURE_LONG &&\n'
                 '\t    sp == 0 && !ui_st.entry && view->ch.mode == RADIO_MODE_FM) {\n'
                 '\t\tstudio_p25_toggle();\n'
                 '\t\tui_toast(studio_p25_active() ? "P25 RX requested" : "FM RX requested");\n'
                 '\t\tdirty = true;\n'
                 '\t\treturn;\n'
                 '\t}\n'
                 '\tif (ev->action == ACT_CONTEXT && ev->gesture == GESTURE_LONG) {\n'
                 '\t\tif (!CONFIG_DMR || view->ch.mode != RADIO_MODE_DMR)')


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    apply(parser.parse_args().tree)
