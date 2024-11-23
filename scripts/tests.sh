#!/bin/bash
set -e

if [ ! -d ".venv_dev" ]; then
    echo "Virtual environment not found. Running build script..."
    ./scripts/build_dev.sh
fi

.venv_dev/bin/python -m unittest discover -s tests --failfast -v
