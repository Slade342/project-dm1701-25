#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
.venv/bin/python firmware-lab/install.py
read -r -p "Press Return to close. "
