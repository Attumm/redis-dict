#!/bin/bash
# Installs the local package into a fresh venv with pip and runs a simple test against it.
set -e
cd "$(dirname "$0")/.."

rm -rf test_install_0.1.0
mkdir test_install_0.1.0
cd test_install_0.1.0
python3 -m venv venv
./venv/bin/pip install -e ..
./venv/bin/python ../tests/misc/tests_simple.py
