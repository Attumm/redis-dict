#!/bin/bash
set -e

rm -rf docs/build/*
rm -rf docs/source/*

#python3 -m venv docs_venv

source dev_venv/bin/activate
#pip install --upgrade pip
#pip install -e ".[docs]"

#echo "Checking docstring style..."

#echo "Checking docstring arguments..."

python3 scripts/generate_sphinx_config.py

sphinx-apidoc -o docs/source src

cd docs
make html

echo "Documentation built successfully in docs/build/html/"
