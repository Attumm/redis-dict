#!/bin/bash
set -e

rm -rf dev_venv
python3 -m venv dev_venv
source dev_venv/bin/activate

pip install --upgrade pip
pip install -e ".[dev]"

python -m mypy
python -m pylama -i E501,E231 src
python -m unittest discover -s tests

deactivate
