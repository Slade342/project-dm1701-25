# Project DM1701-25

Standalone Windows/macOS CPS for the Baofeng DM-1701 / Retevis RT84 family.

The channel editor supports FM, DMR, and an experimental P25 Phase 1
conventional receive channel. P25 channels expose NAC, talkgroup, speaker
audio, and three admission choices: `NAC + talkgroup`, `NAC only`, and `No
filter`. `No filter` sends NAC=ANY/TG=ANY and asks the radio's zone scanner to
walk the selected receive-only channels.

The matching optional firmware image contains the P25 framing/FEC and fixed
point IMBE decoder and the board speaker path. It is a real flashable
experimental image, but the C6000 RF path, first boot, timing, and speaker
output still require validation on a physical DM-1701. It is receive-only;
there is no P25 transmitter, encryption, trunk following, or Phase 2 support.

# Install the single `Project-DM1701-25-Setup-0.4.exe` package. It creates a desktop
shortcut and launches `project_dm1701_25` directly; there is no folder of runners
for the normal user workflow.

