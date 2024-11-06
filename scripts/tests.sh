#!/bin/bash
set -e

python3 -m venv .venv_dev
source .venv_dev/bin/activate

python -m unittest discover -s tests

deactivate
