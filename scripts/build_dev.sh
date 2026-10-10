#!/bin/bash
set -e

source "$(dirname "$0")/lib/env.sh"
resolve_use_uv "$1"

setup_env .venv_dev dev
