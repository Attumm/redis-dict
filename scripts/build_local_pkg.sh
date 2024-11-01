#!/bin/bash
mkdir test_install_0.1.0
cd test_install_0.1.0
python3 -m venv venv
./venv/bin/pip install -e ..
./venv/bin/python ../tests/misc/simple_test.py
