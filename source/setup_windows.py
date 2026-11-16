"""Visible, logged Windows setup; uses only the standard library."""
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parent

def main():
    with (ROOT / 'setup-windows.log').open('w', encoding='utf-8') as log:
        def report(message):
            print(message, flush=True)
            log.write(message + '\n'); log.flush()
        def run(arguments):
            report('Running: ' + subprocess.list2cmdline(arguments))
            with subprocess.Popen(arguments, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding='utf-8', errors='replace', bufsize=1) as process:
                for line in process.stdout:
                    report(line.rstrip())
                if process.wait():
                    raise RuntimeError('Command failed; see the messages immediately above.')
        try:
            report('Python: ' + sys.version.replace('\n', ' '))
            report('Interpreter: ' + sys.executable)
            if sys.version_info < (3, 10):
                raise RuntimeError('Install Python 3.10 or newer from python.org.')
            import tkinter
            report('[2/4] Creating the local Python environment. This may take a minute.')
            run([sys.executable, '-u', '-m', 'venv', str(ROOT / '.venv')])
            python = ROOT / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
            report('[3/4] Downloading dependencies. An internet connection is required.')
            run([str(python), '-u', '-m', 'pip', '--disable-pip-version-check', 'install',
                 '--timeout', '30', '--retries', '2', '-r', str(ROOT / 'requirements.txt')])
            report('[4/4] Checking the application dependencies.')
            run([str(python), '-c', 'import tkinter, yaml, customtkinter, serial, usb.core; print("Dependencies ready.")'])
            report('Setup complete. Open Start-Windows.cmd.')
            return 0
        except Exception:
            report(traceback.format_exc())
            report('Setup failed. Share setup-windows.log so the exact cause can be diagnosed.')
            return 1

if __name__ == '__main__':
    raise SystemExit(main())
