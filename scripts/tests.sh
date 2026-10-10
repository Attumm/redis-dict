#!/bin/bash
set -e
cd "$(dirname "$0")/.."

if [ ! -d ".venv_dev" ]; then
    echo "Virtual environment not found. Running build script..."
    bash scripts/build_dev.sh
fi

.venv_dev/bin/python -m unittest discover -s tests --failfast -v
