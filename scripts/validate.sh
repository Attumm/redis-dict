#!/bin/bash
set -e

python3 -m venv .venv_dev
source .venv_dev/bin/activate

PACKAGE_PATH=$(python3 -c 'import tomli; print(tomli.load("pyproject.toml")["tool"]["scripts"]["package_path"])')


# Type Check
python -m mypy

# Doctype Check
darglint "$PACKAGE_PATH"

# Security Check
bandit -r "$PACKAGE_PATH"

# Multiple linters
python -m pylama -i E501,E231 src

# Unit tests
python -m unittest discover -s tests

# Docstring Check
# pydocstyle src/redis_dict/

deactivate
