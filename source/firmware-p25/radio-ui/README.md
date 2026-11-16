# DM-1701 Studio radio display

This original compact professional-radio home display uses the board's reported
visible area. The DM-1701 has 160 x 120 visible pixels; five-pixel left and right
safe-area insets leave a 150 x 120 drawing viewport. No content is placed in the
eight hidden bottom panel rows.

The home screen displays status, signal bars, battery, zone, channel name,
receive/transmit frequency, mode-specific settings, and the current receiver
state. P25 shows measured NAC, talkgroup and source ID only when the receiver
reports them. The labels `SEARCHING - EXPERIMENTAL` and `MODEM ERROR` are live
states, rather than indications of successful voice reception.

The bottom labels match the physical keys: OK opens the menu, holding # on an
FM channel toggles experimental P25 receive, and * opens Quick settings. Holding
# on a DMR channel keeps the normal talkgroup picker. The receiver runtime owns
all RF operations and the transmit inhibit; this renderer only reads snapshots.

`apply_radio_ui.py` copies the renderer and inserts the hooks into an isolated
RadioFoundry derivative tree. The original upstream checkout remains unchanged.
MIT RadioFoundry notices and the applicable font licenses accompany the combined
firmware release. The new overlay is GPL-3.0-or-later.
