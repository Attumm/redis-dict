#!/bin/bash
set -e

# Adds whitespaces to ":", "," within f strings for some reason
.venv_dev/bin/autopep8 --ignore E203,E225,E231 src/ 
