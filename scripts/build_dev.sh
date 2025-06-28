#!/bin/bash
set -e

USE_UV_FLAG=false

case "${USE_UV}" in
    [Tt]rue|[Tt]|[Yy]es|[Yy])
        USE_UV_FLAG=true
        ;;
esac

case "${1}" in
    [Tt]rue|[Tt]|[Yy]es|[Yy])
        USE_UV_FLAG=true
        ;;
esac

if [ "$USE_UV_FLAG" = true ]; then
    echo "Using UV..."

    if [ ! -d ".venv_dev" ]; then
        echo "Creating virtual environment..."
        uv venv .venv_dev
    fi

    uv pip install --python .venv_dev/bin/python -e ".[dev]"

else
    echo "Using traditional pip/venv..."

    rm -rf .venv_dev
    python3 -m venv .venv_dev
    source .venv_dev/bin/activate

    pip install --upgrade pip
    pip install -e ".[dev]"

    deactivate
fi