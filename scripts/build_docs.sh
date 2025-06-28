#!/bin/bash
set -e

USE_UV_FLAG=false

# Check environment variable
case "${USE_UV}" in
    [Tt]rue|[Tt]|[Yy]es|[Yy])
        USE_UV_FLAG=true
        ;;
esac

# Check command line argument
case "${1}" in
    [Tt]rue|[Tt]|[Yy]es|[Yy])
        USE_UV_FLAG=true
        ;;
esac

# Clean up existing docs
rm -rf docs/Makefile docs/build/* docs/source/*

if [ "$USE_UV_FLAG" = true ]; then
    echo "Using UV for docs..."

    if [ ! -d ".venv_docs" ]; then
        echo "Creating virtual environment..."
        uv venv .venv_docs
    fi

    uv pip install --python .venv_docs/bin/python -e ".[docs]"

else
    echo "Using traditional pip/venv for docs..."

    rm -rf .venv_docs
    python3 -m venv .venv_docs

    source .venv_docs/bin/activate
    pip install --upgrade pip
    pip install -e ".[docs]"

    deactivate
fi

source .venv_docs/bin/activate

python3 scripts/generate_sphinx_config.py

sphinx-apidoc -o docs/source src/redis_dict

cd docs
make html