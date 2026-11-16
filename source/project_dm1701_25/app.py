"""Project DM1701-25 application entry point.

The editor and USB adapter live in the same standalone distribution; this
module is the only application entry point exposed by the new product.
"""

from __future__ import annotations

import os

os.environ.setdefault("PROJECT_DM1701_NAME", "Project DM1701-25")
os.environ.setdefault("PROJECT_DM1701_SHORT", "DM1701-25")
os.environ.setdefault("PROJECT_DM1701_BUILD_LABEL", "0.4 EXPERIMENTAL")

from dm1701.app import Studio, ChannelDialog, main  # noqa: E402,F401

__all__ = ["Studio", "ChannelDialog", "main"]

