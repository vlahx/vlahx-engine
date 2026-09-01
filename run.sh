#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
pip install -r requirements.txt >/dev/null 2>&1 || true

# Rulăm același entrypoint Python ca și în Docker!
exec python run.py
