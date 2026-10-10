#!/bin/bash
set -e
cd "$(dirname "$0")/.."

source scripts/lib/env.sh
resolve_use_uv "$1"

setup_env .venv_dev dev
source .venv_dev/bin/activate

# Type Check
python -m mypy

# Doctype Check
darglint src/redis_dict/

# Security Check
bandit -r src/redis_dict

# Multiple linters
python -m pylama -i E501,E231 src

# Unit tests
python -m unittest discover -s tests

# Docstring Check
pydocstyle src/redis_dict/

deactivate
