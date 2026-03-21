#!/usr/bin/env bash
# scripts/run_demo.sh
# Quick-start the viewer with a synthetic sphere volume.
# Usage: bash scripts/run_demo.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

cd "$ROOT"

if [ ! -d ".venv" ]; then
    echo "No .venv found.  Creating virtual environment …"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "Launching Medical Slice Viewer in demo mode …"
python main.py --demo