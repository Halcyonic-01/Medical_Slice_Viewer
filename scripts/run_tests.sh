#!/usr/bin/env bash
# scripts/run_tests.sh
# Run the full test suite with coverage.
# Usage: bash scripts/run_tests.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "Running tests …"
pytest tests/ \
    --tb=short \
    -v \
    --cov=src \
    --cov-report=term-missing \
    --ignore=tests/test_ui.py   # UI tests require a display server