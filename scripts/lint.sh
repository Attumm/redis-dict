#!/bin/bash
set -e
cd "$(dirname "$0")/.."

source scripts/lib/env.sh
resolve_use_uv "$1"

ensure_env .venv_dev dev

source .venv_dev/bin/activate

# Type Check
python -m mypy

# Doctype Check
darglint src/redis_dict/

# Style checks: pycodestyle, pyflakes, mccabe (the same checks pylama ran)
python scripts/lib/style_checks.py src/redis_dict

# Security Check
bandit -r src/redis_dict

# Docstring Check
pydocstyle src/redis_dict/

# Pylint
pylint src/

deactivate
