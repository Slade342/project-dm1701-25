# Single Windows setup

`build_setup.py` produces `DM1701-Studio-Setup-0.3.exe`. It uses NSIS to package
the application, its supplied source and licenses, the official signed Python
3.12.10 x64 installer, and Windows wheels for every application dependency.

Setup first uses an existing 64-bit Python 3.12 installation with Tk when available.
Otherwise it verifies and runs the included Python installer. It prepares a
local application environment without downloading pip packages, creates desktop
and Start menu shortcuts, and offers to open Studio. It does not flash a radio
during application installation.

The built setup is unsigned; Windows execution remains untested on the Linux
build host. Windows bootloader driver installation is still handled by Windows
and is separate from the desktop application setup.

Build on Linux:

```sh
python3 packaging-windows/build_setup.py
```

For a setup file below a 25 MiB static-host limit, use
`python3 packaging-windows/build_setup.py --web-bootstrap`. It excludes the
firmware debug files and separately hosted derivative source archive, while
including the CPS, complete voice image, Studio source and offline dependency
wheels. If Python 3.12 x64 is absent, setup downloads its pinned official
installer automatically, then checks its SHA-256 and Windows signature before
running it. No manual file selection is required. This variant needs an internet
connection for Python when absent and for the firmware donor during flashing.

Build assets are kept outside the source tree in `../windows-setup-assets` and
the compiler in `../windows-setup-tools`. Python's pinned SHA-256 is checked at
build time and Windows checks its Authenticode signature before installation.
The setup executable's build report records its SHA-256 and exact byte count.
