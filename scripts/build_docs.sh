#!/bin/bash
set -e

source "$(dirname "$0")/lib/env.sh"
resolve_use_uv "$1"

rm -rf docs/Makefile docs/build/* docs/source/*

setup_env .venv_docs docs

source .venv_docs/bin/activate

if [ "$USE_UV" = true ]; then
    uv pip freeze --python .venv_docs/bin/python
else
    pip freeze
fi

python3 scripts/generate_sphinx_config.py

sphinx-apidoc -o docs/source src/redis_dict

cd docs
make html
