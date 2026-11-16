# Windows setup

The same desktop editor runs on Windows and macOS. Windows launchers are supplied;
no prebuilt or signed `.exe` is included. Windows execution and USB access have
not been tested in this environment.

1. Install Python 3.10+ from [python.org](https://www.python.org/downloads/windows/),
   including Tk and the Python launcher.
2. Extract the entire folder and run `Setup-Windows.cmd` once.
3. Run `Start-Windows.cmd`.

The editor works immediately without USB dependencies. For live radio programming,
the current Windows route uses qdmr's Linux `dmrconf` inside WSL2 and USB forwarding.
An independently provided native Windows `dmrconf.exe` can also be selected, but
this package does not supply or validate such a build.

The **capture-lab installer and capture test** use native Windows USB/COM access,
not WSL. Read `firmware-lab/README.md` before installing that experimental image.
It is a raw-data test build, not working P25 voice firmware. Detach the radio
from WSL before using those native tools.

## Connect the USB programming backend

Follow Microsoft's current [WSL USB instructions](https://learn.microsoft.com/windows/wsl/connect-usb).
Install WSL2 with a current Ubuntu distribution and the `usbipd-win` package
described there. These are system installations you perform yourself. In Ubuntu:

```sh
sudo apt update
sudo apt install qdmr
dmrconf --version
```

Require qdmr 0.13.0 or later; 0.15.1 is recommended. Older Ubuntu releases may
provide an older qdmr, so check the version. Set the Ubuntu distribution containing
qdmr as WSL's default distribution if you have more than one.

With the powered-on DM-1701 attached, use the bus ID shown by `usbipd list`:

```powershell
usbipd list
usbipd bind --busid YOUR-BUS-ID
usbipd attach --wsl --busid YOUR-BUS-ID
wsl --exec dmrconf --version
wsl --exec dmrconf detect
```

`bind` needs an Administrator terminal; use the Microsoft instructions for the
current privilege requirements. The radio belongs to WSL while attached and
cannot simultaneously be used by a Windows CPS. USB forwarding may need to be
reattached after unplugging or restarting the radio. Install Linux USB permissions
as described by qdmr if its detection command reports access denied.

Leave Studio's executable field blank. It probes native `dmrconf` first; on
Windows it falls back to `wsl.exe --exec dmrconf` when native qdmr is missing or
cannot answer `--version`. Paths are translated with
`wslpath` using argument arrays, preserving spaces. Automatic detection works
once the radio is visible to that backend. The app does not install WSL, bind USB
devices, modify drivers or request administrator rights automatically.

This is a practical compatibility route, with more setup than native macOS.
The P25 C workbench can also be built inside WSL using `build-essential` and
Python 3. Its host tests still do not prove on-radio P25 operation.
