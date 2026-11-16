#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
echo "Setting up DM-1701 Studio in this folder…"
studio_python=""
for candidate in python3.13 /opt/local/bin/python3.13 /opt/homebrew/bin/python3.13 /usr/local/bin/python3.13 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys, tkinter; assert sys.version_info >= (3,10)' >/dev/null 2>&1; then
        studio_python="$candidate"
        break
    fi
done
if [ -z "$studio_python" ]; then
    echo "Install Python 3.10+ with Tk support. See README.md for macOS instructions."
    read -r -p "Press Return to close. "
    exit 1
fi
"$studio_python" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x run.command 'DM-1701 Studio.app/Contents/MacOS/launch'
echo "Setup complete. Double-click DM-1701 Studio.app or run.command."
echo "For USB programming also install qdmr; see README.md."
read -r -p "Press Return to close. "
