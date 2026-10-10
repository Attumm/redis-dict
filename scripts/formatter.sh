#!/bin/bash
set -e
cd "$(dirname "$0")/.."

if [ ! -d ".venv_dev" ]; then
    echo "Virtual environment not found. Running build script..."
    bash scripts/build_dev.sh
fi

# Adds whitespaces to ":", "," within f strings for some reason
.venv_dev/bin/autopep8 --ignore E203,E225,E231 src/
