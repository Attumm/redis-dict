#!/bin/bash
set -e
cd "$(dirname "$0")/.."

source scripts/lib/env.sh
source scripts/lib/checks.sh
resolve_use_uv "$1"

ensure_env .venv_dev dev

source .venv_dev/bin/activate

# Type Check
python -m mypy

# Doctype Check
darglint src/redis_dict/

# Style checks: pycodestyle, pyflakes, mccabe (complexity limit 10)
python -m pycodestyle src/redis_dict
python -m pyflakes src/redis_dict
check_complexity src/redis_dict/*.py

# Unit tests & 100% branch coverage gate
python -m coverage run -m unittest discover -s tests
python -m coverage report --fail-under=100

# Security Check
bandit -r src/redis_dict

# Docstring Check
pydocstyle src/redis_dict/

deactivate
