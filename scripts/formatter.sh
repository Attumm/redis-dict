#!/bin/bash
set -e
cd "$(dirname "$0")/.."

source scripts/lib/env.sh
resolve_use_uv "$1"

ensure_env .venv_dev dev

# Adds whitespaces to ":", "," within f strings for some reason
.venv_dev/bin/autopep8 --ignore E203,E225,E231 src/
