#!/bin/bash
set -e

if [ ! -d ".venv_dev" ]; then
    echo "Virtual environment not found. Running build script..."
    bash ./scripts/build.sh
fi

# Adds whitespaces to ":", "," within f strings for some reason.
# Should be reported to autopep8.
.venv_dev/bin/autopep8 --ignore E203,E225,E231 src/
