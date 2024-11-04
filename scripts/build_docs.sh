#!/bin/bash
set -e

rm -rf docs/Makefile docs/build/* docs/source/*

python3 -m venv .venv_docs

source .venv_docs/bin/activate
pip install --upgrade pip
pip install -e ".[docs]"

pip freeze

python3 scripts/generate_sphinx_config.py

sphinx-apidoc -o docs/source src/redis_dict

cd docs
make html
