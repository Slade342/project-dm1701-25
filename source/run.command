#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
if [ -x .venv/bin/python ]; then
    exec .venv/bin/python -m dm1701
fi
exec python3 -m dm1701
