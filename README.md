# Project DM1701-25

Project DM1701-25 is a standalone CPS and experimental P25 Phase 1 receive
firmware project for the Baofeng DM-1701 / Retevis RT84 family.

The public download page is published with GitHub Pages at:

`https://slade342.github.io/project-dm1701-25/`

The page provides the Windows setup, macOS app bundle, P25 firmware image,
source archives, and SHA-256 checksums. The `source/` directory contains the
corresponding source tree.

## Important P25 notice

The P25 image is experimental and RX-only. It includes protocol/FEC and IMBE
decoder work plus speaker integration, but over-air reception and real-time
timing have not been verified on a physical DM-1701. Make a complete flash and
calibration backup before attempting any firmware operation.

The firmware source includes third-party notices and license files. The
portable P25 implementation retains its upstream provenance; this rename does
not claim ownership of those components.
