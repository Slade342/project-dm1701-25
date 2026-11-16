"""Conservative qdmr/dmrconf bridge; no firmware flashing.

Commands and names were checked against hmatuschek/qdmr v0.15.1. USB
operations use auto-detection and never override the connected radio type.
OpenGD77 reports a firmware family, not the physical model or serial number.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Callable
import uuid


class BackendError(RuntimeError):
    """An operation could not safely finish."""


@dataclass(frozen=True)
class BackupResult:
    yaml_path: Path
    binary_path: Path
    detected: str
    log: str


@dataclass(frozen=True)
class WriteResult:
    backup: BackupResult
    log: str


# Exact radio->name() strings from qdmr v0.15.1, not --list-radios labels.
_PROFILES = {
    "stock": ("dm1701", "Baofeng DM-1701"),
    "opengd77": ("openuv380", "Open MD-UV380"),
}
_MIN_VERSION = (0, 13, 0)
_USB_LOCK = threading.RLock()


def find_executable(configured: str | None = None) -> str:
    """Locate dmrconf in an explicit path, PATH, or normal install prefixes."""
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            raise BackendError("The configured dmrconf path must be absolute.")
        candidates = [str(path)]
    else:
        on_path = shutil.which("dmrconf")
        candidates = ([on_path] if on_path else []) + [
            "/opt/homebrew/bin/dmrconf", "/usr/local/bin/dmrconf", "/opt/local/bin/dmrconf",
        ]
        if os.name == "nt":
            for root_name in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
                root = os.environ.get(root_name)
                if root:
                    candidates.append(str(Path(root) / "qdmr" / "dmrconf.exe"))
            profile = os.environ.get("USERPROFILE")
            if profile:
                candidates.append(str(Path(profile) / "scoop" / "shims" / "dmrconf.exe"))
    for candidate in candidates:
        if Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(Path(candidate).resolve())
    raise BackendError(
        "dmrconf was not found. Install qdmr 0.13.0 or newer (0.15.1 recommended), "
        "then choose its executable under Radio & backups. On Windows, qdmr in WSL2 "
        "can be selected instead. The channel editor works without a programmer."
    )


def _process_text(value) -> str:
    """Keep Windows launcher errors readable, including UTF-16 WSL output."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        encoding = "utf-16" if value.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
        if encoding == "utf-8" and value[:200].count(b"\x00") > len(value[:200]) // 5:
            encoding = "utf-16-le"
        return value.decode(encoding, errors="replace").strip()
    # subprocess's UTF-8 decoder can leave an ASCII UTF-16 error full of NULs.
    return str(value).replace("\x00", "").lstrip("\ufeff").strip()


def create_backend(configured: str | None = None, timeout: float = 180, *,
                   mode: str = "auto", runner: Callable = subprocess.run) -> "Backend":
    """Select a working programmer using offline checks; call from a worker.

    Auto tries the native tool and, on Windows, WSL qdmr. A supplied executable
    is an explicit choice: a broken path is never silently replaced. No radio
    is opened by this function; probe() runs only --version/--list-radios.
    """
    if mode not in ("auto", "native", "wsl"):
        raise BackendError("Choose Automatic, Native dmrconf, or WSL qdmr as the programmer.")
    choices = [mode] if mode != "auto" else ["native"]
    if mode == "auto" and not configured and sys.platform == "win32":
        choices.append("wsl")
    failures = []
    for transport in choices:
        try:
            backend = Backend(configured, timeout, runner=runner, use_wsl=transport == "wsl")
            backend.probe()
            return backend
        except BackendError as exc:
            failures.append(f"{transport}: {exc}")
    raise BackendError("No working codeplug programmer is available.\n" + "\n\n".join(failures)
                       + "\nThe radio firmware was not changed. See WINDOWS.md for WSL/USB setup.")


class Backend:
    """Blocking adapter; call from a worker thread to keep a GUI responsive.

    A binary codeplug and decoded YAML backup precede every write. These are
    codeplug backups only, not radio firmware or calibration/flash backups.
    """

    def __init__(self, executable: str | None = None, timeout: float = 180,
                 *, runner: Callable = subprocess.run, use_wsl: bool | None = None):
        self.wsl = bool(use_wsl)
        if self.wsl:
            self.executable = executable or shutil.which("wsl.exe") or "wsl.exe"
        else:
            try:
                self.executable = find_executable(executable)
            except BackendError:
                # Do not silently route Windows radio operations through WSL. A
                # missing Linux dmrconf otherwise appears as unsigned exit
                # 4294967295 and looks like a radio/firmware failure. WSL can
                # still be selected explicitly with use_wsl=True.
                raise
        self.timeout = timeout
        self._runner = runner
        self._probed = False
        self._lock = threading.Lock()
        self._version_text = ""
        self._history: list[str] = []

    @property
    def transport_label(self) -> str:
        return "WSL qdmr" if self.wsl else "Native dmrconf"

    @property
    def diagnostics(self) -> str:
        """Recent command and response text, suitable for an operation log."""
        return "\n\n".join(self._history[-30:])

    @staticmethod
    def _check_codeplug_interface() -> None:
        from .discovery import native_lab_port
        port = native_lab_port()
        if port:
            raise BackendError(
                f"The connected radio is running RadioFoundry/Studio experimental firmware on {port}. "
                "This serial interface does not support the stock/OpenGD77 qdmr codeplug reader. "
                "Use the experimental firmware's channel controls instead. To read an OpenGD77 "
                "codeplug, first boot a radio that is actually running OpenGD77. No write was attempted."
            )

    @staticmethod
    def _profile(profile: str) -> tuple[str, str]:
        try:
            return _PROFILES[profile]
        except KeyError:
            raise BackendError("Select stock or OpenGD77 firmware before a radio operation.") from None

    def _run(self, args: list[str]) -> str:
        arguments = list(map(str, args))
        if self.wsl:
            translated = []
            for arg in arguments:
                if PureWindowsPath(arg).is_absolute() and PureWindowsPath(arg).drive:
                    try:
                        converted = self._runner([self.executable, "--exec", "wslpath", "-a", "-u", arg],
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=self.timeout, check=False)
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        raise BackendError(f"WSL path conversion failed: {exc}") from exc
                    converted_path = _process_text(converted.stdout)
                    if converted.returncode or not converted_path.startswith("/"):
                        detail = _process_text(converted.stderr) or converted_path
                        raise BackendError(f"WSL could not access the codeplug path. See WINDOWS.md.\n{detail}")
                    translated.append(converted_path)
                else:
                    translated.append(arg)
            command = [self.executable, "--exec", "dmrconf", *translated]
        else:
            command = [self.executable, *arguments]
        shown_command = subprocess.list2cmdline(command)
        self._history.append(f"{self.transport_label}: {shown_command}")
        try:
            result = self._runner(command, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=self.timeout,
                                  check=False)
        except subprocess.TimeoutExpired as exc:
            raise BackendError(
                f"dmrconf timed out after {self.timeout:g} seconds. If a write was in "
                "progress its result is uncertain; inspect/read the radio before retrying."
            ) from exc
        except OSError as exc:
            raise BackendError(f"Could not start {self.transport_label}: {exc}\nCommand: {shown_command}") from exc
        output = "\n".join(part for part in (_process_text(result.stdout), _process_text(result.stderr)) if part)
        self._history[-1] += f"\nExit: {result.returncode}\n{output or '(no output)'}"
        if result.returncode:
            code = result.returncode
            if code > 0x7fffffff:
                code -= 0x100000000
            hint = ""
            if code == -1:
                hint = (" The programmer process could not start or exited with -1. "
                        + ("Open Windows Terminal and run wsl --exec dmrconf --version; install "
                           "qdmr in the default WSL distribution if that command fails. " if self.wsl else
                           "Check that the selected dmrconf.exe can run with its required DLLs, "
                           "or choose WSL qdmr. ")
                        + "This process failure does not establish a radio firmware fault.")
            elif code in (-1073741515, -1073741701):
                hint = " Windows could not load this executable or a required DLL. Reinstall the matching qdmr build."
            elif self.wsl and ("detect" in arguments or "read" in arguments):
                hint = " Make sure the powered-on radio is attached to WSL with usbipd and no other CPS has it open."
            raise BackendError(f"dmrconf {' '.join(args[:2])} failed (exit {code}).{hint}\n"
                               f"Command: {shown_command}\n{output or '(no output)'}")
        return output

    def probe(self) -> str:
        """Verify a usable CLI version and required offline radio profiles."""
        with self._lock:
            return self._probe()

    def _probe(self) -> str:
        if self._probed:
            return self._version_text
        version = self._run(["--version"])
        match = re.search(r"\b(\d+)\.(\d+)(?:\.(\d+))?\b", version)
        if not match or tuple(int(x or 0) for x in match.groups()) < _MIN_VERSION:
            raise BackendError(f"qdmr/dmrconf 0.13.0 or newer is required. Reported: {version or '(empty)'}")
        supported = self._run(["--list-radios"])
        for key, _ in _PROFILES.values():
            if not re.search(rf"(?m)^\s*{re.escape(key)}\s*\|", supported):
                raise BackendError(f"This dmrconf build does not list the required '{key}' radio profile.")
        self._probed = True
        self._version_text = version
        return version

    def _detect(self, profile: str) -> tuple[str, str]:
        _, expected = self._profile(profile)
        self._check_codeplug_interface()
        self._probe()
        output = self._run(["detect"])
        found = re.findall(r"(?m)^Found:\s*(.+?)\s*$", output)
        if len(found) != 1 or found[0] != expected:
            actual = ", ".join(found) or output or "no identifiable radio"
            raise BackendError(f"Selected firmware expects '{expected}', but detected '{actual}'. No write was attempted.")
        return found[0], output

    def detect(self, profile: str) -> str:
        with _USB_LOCK, self._lock:
            name, _ = self._detect(profile)
            return name

    def identify(self) -> tuple[str, str]:
        """Automatically identify a supported connected firmware family, read-only."""
        with _USB_LOCK, self._lock:
            self._check_codeplug_interface()
            self._probe()
            output = self._run(["detect"])
            found = re.findall(r"(?m)^Found:\s*(.+?)\s*$", output)
            if len(found) != 1:
                raise BackendError("No single supported radio was detected. Check the cable and power.")
            for profile, (_, name) in _PROFILES.items():
                if found[0] == name:
                    return profile, name
            raise BackendError(f"Connected radio is outside this app's profiles: {found[0]}")

    @staticmethod
    def _input(path: str | Path) -> Path:
        result = Path(path).expanduser().resolve()
        if not result.is_file() or result.stat().st_size == 0:
            raise BackendError(f"The YAML codeplug does not exist or is empty: {result}")
        return result

    def _verify(self, yaml_path: str | Path, profile: str) -> str:
        key, _ = self._profile(profile)
        self._probe()
        source = self._input(yaml_path)
        if profile == "opengd77":
            # qdmr 0.15.1 OpenUV380's offline verify constructs the radio with
            # a null device, then dereferences it in extendedCallsignDB().
            # Syntax validation and actual model-specific encoding avoid that
            # reproducible upstream crash; they are not its limit verifier.
            from .model import Codeplug
            document = Codeplug.load(source)
            issues = document.validate()
            if len(document.data.get("channels", [])) > 1024:
                issues.append("OpenUV380 supports at most 1024 channels.")
            if issues:
                raise BackendError("Codeplug checks failed:\n" + "\n".join(issues))
            parsed = self._run(["--yaml", "verify", str(source)])
            with tempfile.TemporaryDirectory(prefix="dm1701-preflight-") as scratch:
                compiled = Path(scratch) / "check.dfu"
                encoded = self._run(["--yaml", "--radio", key, "encode", str(source), str(compiled)])
                if not compiled.is_file() or not compiled.stat().st_size:
                    raise BackendError("OpenUV380 preflight did not produce a binary codeplug.")
            return "\n".join(part for part in (parsed, encoded,
                "OpenUV380 syntax, local checks and model encoding passed. Its offline limit verifier is avoided because qdmr 0.15.1 crashes there.") if part)
        output = self._run(["--yaml", "--radio", key, "verify", str(source)])
        return output or "qdmr verified the codeplug successfully."

    def verify(self, yaml_path: str | Path, profile: str) -> str:
        """Offline syntax, reference, and selected-radio limit verification."""
        with self._lock:
            return self._verify(yaml_path, profile)

    def encode(self, yaml_path: str | Path, output_path: str | Path, profile: str) -> str:
        """Compile offline to qdmr DFU format, not manufacturer .rdt or firmware."""
        with self._lock:
            source = self._input(yaml_path)
            target = Path(output_path).expanduser().resolve()
            if source == target:
                raise BackendError("The compiled output must differ from the YAML source.")
            key, _ = self._profile(profile)
            # Snapshot stops edits to the source changing it between verification and encode.
            with tempfile.TemporaryDirectory(prefix="dm1701-encode-") as scratch:
                snapshot = Path(scratch) / "codeplug.yaml"
                shutil.copyfile(source, snapshot)
                verified = self._verify(snapshot, profile)
                partial = Path(scratch) / "codeplug.dfu"
                output = self._run(["--yaml", "--radio", key, "encode", str(snapshot), str(partial)])
                if not partial.is_file() or partial.stat().st_size == 0:
                    raise BackendError("dmrconf reported success but did not create a non-empty DFU codeplug.")
                target.parent.mkdir(parents=True, exist_ok=True)
                # Target-local temporary file gives atomic replacement across filesystems.
                handle, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
                os.close(handle)
                try:
                    shutil.copyfile(partial, name)
                    os.replace(name, target)
                finally:
                    Path(name).unlink(missing_ok=True)
            return "\n".join(x for x in (verified, output, f"Compiled codeplug: {target}") if x)

    def _read(self, backup_dir: str | Path, profile: str) -> BackupResult:
        detected, detect_log = self._detect(profile)
        folder = Path(backup_dir).expanduser().resolve()
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        prefix = folder / f"DM1701-{profile}-{stamp}-{uuid.uuid4().hex[:6]}"
        binary_path = Path(str(prefix) + ".dfu")
        yaml_path = Path(str(prefix) + ".yaml")
        binary_partial = Path(str(binary_path) + ".partial")
        yaml_partial = Path(str(yaml_path) + ".partial")
        logs = [detect_log]
        try:
            # A binary dump remains available if decoding YAML later fails.
            logs.append(self._run(["--bin", "read", str(binary_partial)]))
            if not binary_partial.is_file() or binary_partial.stat().st_size == 0:
                raise BackendError("The binary codeplug backup is missing or empty. No write was attempted.")
            binary_partial.replace(binary_path)
            logs.append(self._run(["--yaml", "read", str(yaml_partial)]))
            if not yaml_partial.is_file() or yaml_partial.stat().st_size == 0:
                raise BackendError("The YAML codeplug backup is missing or empty. No write was attempted.")
            yaml_partial.replace(yaml_path)
            # The decoded file must also be acceptable to the chosen profile.
            logs.append(self._verify(yaml_path, profile))
            _, final_detect = self._detect(profile)
            logs.append(final_detect)
            manifest = {
                "created_utc": stamp, "firmware_profile": profile,
                "detected_family": detected, "dmrconf_version": self._version_text,
                "binary_codeplug": binary_path.name, "yaml_codeplug": yaml_path.name,
                "scope": "Codeplug only. Not firmware, calibration, or a complete flash backup.",
            }
            Path(str(prefix) + ".json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        except (BackendError, OSError) as exc:
            if binary_path.exists():
                raise BackendError(f"Backup did not fully complete; no write was attempted.\n"
                                   f"The binary codeplug dump is retained at {binary_path}\n{exc}") from exc
            raise
        finally:
            binary_partial.unlink(missing_ok=True)
            yaml_partial.unlink(missing_ok=True)
        return BackupResult(yaml_path, binary_path, detected, "\n".join(x for x in logs if x))

    def read(self, backup_dir: str | Path, profile: str) -> BackupResult:
        """Read and retain both binary and decoded codeplugs from one connected radio."""
        with _USB_LOCK, self._lock:
            try:
                return self._read(backup_dir, profile)
            except (BackendError, OSError) as exc:
                # A failed discovery used to leave only a fleeting dialog.
                # Keep the programmer's actual output even before a dump exists.
                try:
                    folder = Path(backup_dir).expanduser().resolve()
                    folder.mkdir(parents=True, exist_ok=True)
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                    diagnostics = folder / f"DM1701-read-{stamp}.diagnostics.txt"
                    diagnostics.write_text(f"{self.transport_label}\n{exc}\n\n{self.diagnostics}\n", encoding="utf-8")
                except OSError:
                    raise BackendError(f"Read failed: {exc}") from exc
                raise BackendError(f"Read failed: {exc}\nFull programmer details saved to: {diagnostics}") from exc

    def write(self, yaml_path: str | Path, backup_dir: str | Path, profile: str) -> WriteResult:
        """Verify a frozen YAML snapshot, back up the radio, then program it.

        No override, init-codeplug, or ignore-limits flag is supplied. qdmr's
        update mode is used. USB hardware behavior has not been validated here.
        """
        with _USB_LOCK, self._lock:
            source = self._input(yaml_path)
            self._profile(profile)
            with tempfile.TemporaryDirectory(prefix="dm1701-write-") as scratch:
                snapshot = Path(scratch) / "codeplug.yaml"
                shutil.copyfile(source, snapshot)
                verified = self._verify(snapshot, profile)
                backup = self._read(backup_dir, profile)
                _, detection = self._detect(profile)
                try:
                    output = self._run(["--yaml", "write", str(snapshot)])
                except BackendError as exc:
                    raise BackendError(f"Programming failed or is incomplete. Codeplug backups:\n"
                                       f"{backup.binary_path}\n{backup.yaml_path}\n{exc}") from exc
                log = "\n".join(x for x in (verified, backup.log, detection, output,
                    "dmrconf reported that programming completed. Read back the radio to inspect the result.",
                    f"Codeplug backups: {backup.binary_path} and {backup.yaml_path}") if x)
                return WriteResult(backup, log)
