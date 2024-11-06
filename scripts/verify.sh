#!/bin/bash
set -e

rm -rf .venv_dev
python3 -m venv .venv_dev
source .venv_dev/bin/activate

# Type Check
python -m mypy

# Doctype Check
darglint src/redis_dict/

# Multiple linters
python -m pylama -i E501,E231 src

# Unit tests
python -m unittest discover -s tests

# Security Check
 bandit -r src/redis_dict

# Docstring Check
# pydocstyle src/redis_dict/

deactivate
