"""CLI contract tests: qdmr is simulated; no radio USB claims are made."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from dm1701.backend import Backend, BackendError, create_backend, find_executable


class FakeDmrconf:
    def __init__(self):
        self.commands = []
        self.name = "Baofeng DM-1701"
        self.version = "dmrconf 0.15.1"
        self.fail = None
        self.before = None
        self.written = None

    def __call__(self, command, **kwargs):
        args = command[1:]
        self.commands.append(args)
        assert kwargs["capture_output"] and not kwargs["check"]
        assert "shell" not in kwargs
        if self.before:
            self.before(args)
        if self.fail and self.fail(args):
            return subprocess.CompletedProcess(command, 1, "", "simulated transfer failure")
        if args == ["--version"]:
            return subprocess.CompletedProcess(command, 0, self.version, "")
        if args == ["--list-radios"]:
            return subprocess.CompletedProcess(command, 0, " dm1701 | DM-1701\n openuv380 | OpenMDUV380\n", "")
        if args == ["detect"]:
            return subprocess.CompletedProcess(command, 0, f"Found: {self.name}\n", "")
        if "read" in args:
            Path(args[-1]).write_bytes(b"DFU CODEPLUG" if "--bin" in args else b"version: '0.15.1'\nchannels: []\n")
        if "encode" in args:
            Path(args[-1]).write_bytes(b"ENCODED")
        if "write" in args:
            self.written = Path(args[-1]).read_text()
        return subprocess.CompletedProcess(command, 0, "", "")


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "test.yaml"
        self.config.write_text("version: '0.15.1'\nchannels: []\n")
        self.runner = FakeDmrconf()
        self.backend = Backend(sys.executable, runner=self.runner)

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_path_must_be_executable_absolute_file(self):
        with self.assertRaises(BackendError):
            find_executable("relative/dmrconf")
        with self.assertRaises(BackendError):
            find_executable(str(self.config))
        self.assertEqual(str(Path(sys.executable).resolve()), find_executable(sys.executable))

    def test_old_backend_cannot_run_radio_operation(self):
        self.runner.version = "dmrconf 0.12.0"
        with self.assertRaisesRegex(BackendError, "0.13.0"):
            self.backend.detect("stock")
        self.assertFalse(any("detect" in c for c in self.runner.commands))

    def test_backend_must_list_both_supported_profiles(self):
        original = self.runner
        def run(command, **kwargs):
            if command[1:] == ["--list-radios"]:
                return subprocess.CompletedProcess(command, 0, " dm1701 | DM-1701\n", "")
            return original(command, **kwargs)
        backend = Backend(sys.executable, runner=run)
        with self.assertRaisesRegex(BackendError, "openuv380"):
            backend.probe()

    def test_verify_is_offline_and_model_specific(self):
        self.backend.verify(self.config, "opengd77")
        self.assertIn(["--yaml", "verify", str(self.config)], self.runner.commands)
        self.assertTrue(any(command[:4] == ["--yaml", "--radio", "openuv380", "encode"] for command in self.runner.commands))
        self.assertFalse(any(command[:4] == ["--yaml", "--radio", "openuv380", "verify"] for command in self.runner.commands))
        self.assertFalse(any("detect" in c for c in self.runner.commands))

    def test_unselected_profile_rejected(self):
        with self.assertRaises(BackendError):
            self.backend.verify(self.config, "unknown")
        self.assertEqual([], self.runner.commands)

    def test_open_firmware_compile_failure_blocks_all_usb(self):
        self.runner.fail = lambda command: "encode" in command
        with self.assertRaises(BackendError):
            self.backend.write(self.config, self.root / "backups", "opengd77")
        self.assertFalse(any("detect" in command or "write" in command or "read" in command for command in self.runner.commands))

    def test_wrong_detected_firmware_blocks_backup_and_write(self):
        self.runner.name = "Open GD-77"
        with self.assertRaisesRegex(BackendError, "expects"):
            self.backend.write(self.config, self.root / "backups", "stock")
        self.assertFalse(any("write" in c or "read" in c for c in self.runner.commands))

    def test_write_creates_both_backups_then_programs_snapshot(self):
        result = self.backend.write(self.config, self.root / "backups", "stock")
        commands = self.runner.commands
        writes = [i for i, c in enumerate(commands) if "write" in c]
        self.assertEqual(1, len(writes))
        self.assertEqual(2, sum("read" in c for c in commands[:writes[0]]))
        self.assertTrue(result.backup.binary_path.is_file())
        self.assertTrue(result.backup.yaml_path.is_file())
        self.assertIn("Codeplug backups:", result.log)
        for command in commands:
            if "read" in command or "write" in command or "detect" in command:
                self.assertNotIn("--radio", command)
                self.assertNotIn("--init-codeplug", command)
                self.assertNotIn("--ignore-limits", command)

    def test_failed_yaml_backup_retains_binary_and_blocks_write(self):
        self.runner.fail = lambda c: "--yaml" in c and "read" in c
        with self.assertRaisesRegex(BackendError, "binary codeplug dump is retained"):
            self.backend.write(self.config, self.root / "backups", "stock")
        self.assertEqual(1, len(list((self.root / "backups").glob("*.dfu"))))
        self.assertFalse(any("write" in c for c in self.runner.commands))
        self.assertEqual([], list((self.root / "backups").glob("*.partial")))

    def test_failed_verification_blocks_usb_operations(self):
        self.runner.fail = lambda c: "verify" in c
        with self.assertRaises(BackendError):
            self.backend.write(self.config, self.root / "backups", "stock")
        self.assertFalse(any("detect" in c or "read" in c or "write" in c for c in self.runner.commands))

    def test_write_uses_same_snapshot_even_if_user_edits_original(self):
        original = self.config.read_text()
        def edit_during_backup(command):
            if "read" in command:
                self.config.write_text("malformed: later edit")
        self.runner.before = edit_during_backup
        self.backend.write(self.config, self.root / "backups", "stock")
        self.assertEqual(original, self.runner.written)

    def test_read_backup_paths_are_distinct_and_keep_timestamp_suffix(self):
        one = self.backend.read(self.root / "backups", "stock")
        two = self.backend.read(self.root / "backups", "stock")
        self.assertNotEqual(one.binary_path, two.binary_path)
        self.assertNotEqual(one.yaml_path, two.yaml_path)
        self.assertEqual(2, len(list((self.root / "backups").glob("*.json"))))

    def test_opengd77_expected_name_is_firmware_family(self):
        self.runner.name = "Open MD-UV380"
        self.assertEqual("Open MD-UV380", self.backend.detect("opengd77"))

    def test_identify_automatically_selects_supported_family(self):
        self.runner.name = "Open MD-UV380"
        self.assertEqual(("opengd77", "Open MD-UV380"), self.backend.identify())
        self.assertFalse(any("read" in command or "write" in command for command in self.runner.commands))

    def test_identify_rejects_other_radio(self):
        self.runner.name = "Some other radio"
        with self.assertRaisesRegex(BackendError, "outside"):
            self.backend.identify()

    def test_wsl_path_translation_preserves_spaces_without_shell(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            self.assertNotIn("shell", kwargs)
            if command[1:3] == ["--exec", "wslpath"]:
                return subprocess.CompletedProcess(command, 0, "/mnt/c/Users/Radio User/test.yaml\n", "")
            return subprocess.CompletedProcess(command, 0, "ok", "")
        backend = Backend(sys.executable, use_wsl=True, runner=runner)
        self.assertEqual("ok", backend._run(["--yaml", "verify", r"C:\Users\Radio User\test.yaml"]))
        self.assertEqual([sys.executable, "--exec", "dmrconf", "--yaml", "verify", "/mnt/c/Users/Radio User/test.yaml"], calls[-1])

    def test_wsl_path_failure_blocks_command(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 1, "", "not mounted")
        backend = Backend(sys.executable, use_wsl=True, runner=runner)
        with self.assertRaisesRegex(BackendError, "WSL could not access"):
            backend._run(["--yaml", "write", r"C:\codeplug.yaml"])
        self.assertEqual(1, len(calls))

    def test_write_failure_reports_saved_backups(self):
        self.runner.fail = lambda c: "write" in c
        with self.assertRaisesRegex(BackendError, "Programming failed or is incomplete"):
            self.backend.write(self.config, self.root / "backups", "stock")
        self.assertEqual(1, len(list((self.root / "backups").glob("*.dfu"))))

    def test_encode_verifies_and_writes_selected_model(self):
        output = self.root / "compiled.dfu"
        self.backend.encode(self.config, output, "opengd77")
        self.assertEqual(b"ENCODED", output.read_bytes())
        self.assertTrue(any(c[:4] == ["--yaml", "--radio", "openuv380", "encode"] for c in self.runner.commands))
        self.assertFalse(any("detect" in c for c in self.runner.commands))

    def test_encode_rejects_source_overwrite(self):
        with self.assertRaises(BackendError):
            self.backend.encode(self.config, self.config, "stock")

    def test_timeout_raises_actionable_error(self):
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 3)
        backend = Backend(sys.executable, timeout=3, runner=timeout)
        with self.assertRaisesRegex(BackendError, "timed out"):
            backend.probe()

    def test_unsigned_windows_exit_is_reported_as_signed_process_error(self):
        def failed(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0xffffffff, "", "W")
        backend = Backend(sys.executable, runner=failed)
        with self.assertRaisesRegex(BackendError, r"exit -1.*programmer process"):
            backend.probe()

    def test_auto_falls_back_from_broken_native_to_working_wsl_offline(self):
        commands = []
        def runner(command, **kwargs):
            commands.append(command)
            if command[1:2] != ["--exec"]:
                return subprocess.CompletedProcess(command, 0xffffffff, "", "W\x00S\x00L\x00 error")
            args = command[3:]
            text = "dmrconf 0.15.1" if args == ["--version"] else "dm1701 | DM-1701\nopenuv380 | OpenUV380"
            return subprocess.CompletedProcess(command, 0, text, "")
        with patch("dm1701.backend.sys.platform", "win32"), patch("dm1701.backend.find_executable", return_value="native.exe"), patch("dm1701.backend.shutil.which", return_value="wsl.exe"):
            backend = create_backend(runner=runner)
        self.assertTrue(backend.wsl)
        self.assertEqual("WSL qdmr", backend.transport_label)
        self.assertFalse(any("detect" in command or "read" in command for command in commands))

    def test_explicit_broken_native_never_silently_falls_back(self):
        calls = []
        def failed(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0xffffffff, "", "broken")
        with patch("dm1701.backend.sys.platform", "win32"), patch("dm1701.backend.find_executable", return_value="selected.exe"):
            with self.assertRaisesRegex(BackendError, "No working codeplug programmer"):
                create_backend("selected.exe", runner=failed)
        self.assertEqual(1, len(calls))
        self.assertNotIn("--exec", calls[0])

    def test_wsl_utf16_error_is_readable_and_identifies_setup_problem(self):
        def failed(command, **kwargs):
            return subprocess.CompletedProcess(command, 0xffffffff, b"", "WSL unavailable".encode("utf-16"))
        backend = Backend("wsl.exe", use_wsl=True, runner=failed)
        with self.assertRaisesRegex(BackendError, "wsl --exec dmrconf --version") as error:
            backend.probe()
        self.assertIn("WSL unavailable", str(error.exception))
        self.assertIn("Command:", str(error.exception))
        self.assertNotIn("\x00", str(error.exception))

    def test_lab_firmware_refuses_qdmr_read_and_keeps_diagnostics(self):
        with patch("dm1701.discovery.native_lab_port", return_value="COM7"):
            with self.assertRaisesRegex(BackendError, "RadioFoundry/Studio experimental"):
                self.backend.read(self.root / "backups", "opengd77")
        self.assertFalse(self.runner.commands)
        logs = list((self.root / "backups").glob("*.diagnostics.txt"))
        self.assertEqual(1, len(logs))
        self.assertIn("COM7", logs[0].read_text())

    def test_failed_read_saves_actual_programmer_output(self):
        self.runner.fail = lambda args: args == ["detect"]
        with self.assertRaisesRegex(BackendError, "Full programmer details saved"):
            self.backend.read(self.root / "backups", "stock")
        log = next((self.root / "backups").glob("*.diagnostics.txt")).read_text()
        self.assertIn("simulated transfer failure", log)
        self.assertIn("Command:", log)


if __name__ == "__main__":
    unittest.main()
