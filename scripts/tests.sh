#!/bin/bash
set -e
cd "$(dirname "$0")/.."

source scripts/lib/env.sh
resolve_use_uv "$1"

ensure_env .venv_dev dev

.venv_dev/bin/python -m unittest discover -s tests --failfast -v
