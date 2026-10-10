#!/bin/bash
# Shared environment setup, sourced by the build scripts (which first cd to the project root).
#
# uv is used by default and installs the exact versions pinned in uv.lock.
# To use pip/venv instead, set USE_UV=false or pass "false" as the first argument:
#   USE_UV=false ./scripts/build_dev.sh
#   ./scripts/build_dev.sh false
# This works for every script that sets up or uses an environment
# (build_dev, build_dev_checks, build_docs, tests, verify, lint, formatter).
# When uv is not installed, pip/venv is used.
# Install uv: https://docs.astral.sh/uv/getting-started/installation/

resolve_use_uv() {
    USE_UV_FLAG=true

    for value in "${USE_UV}" "${1}"; do
        case "${value}" in
            [Ff]alse|[Ff]|[Nn]o|[Nn]|0)
                USE_UV_FLAG=false
                ;;
        esac
    done

    if [ "$USE_UV_FLAG" = true ] && ! command -v uv >/dev/null 2>&1; then
        echo "uv not found, falling back to pip/venv."
        USE_UV_FLAG=false
    fi

    export USE_UV="$USE_UV_FLAG"
}

# Create or update a virtual environment with the project and the given extras.
# Usage: setup_env <venv_dir> <extra> [<extra> ...]
setup_env() {
    local venv_dir="$1"
    shift

    if [ "$USE_UV_FLAG" = true ]; then
        echo "Using uv..."
        local extra_args=()
        for extra in "$@"; do
            extra_args+=(--extra "$extra")
        done
        UV_PROJECT_ENVIRONMENT="$venv_dir" uv sync --locked "${extra_args[@]}"
    else
        echo "Using pip/venv..."
        local extras
        extras=$(IFS=,; echo "$*")
        rm -rf "$venv_dir"
        python3 -m venv "$venv_dir"
        "$venv_dir/bin/pip" install --upgrade pip
        "$venv_dir/bin/pip" install -e ".[$extras]"
    fi
}

# Make sure the environment is ready before running tools in it.
# uv: always sync, which is fast and keeps the environment equal to uv.lock.
# pip/venv: only build the environment when it doesn't exist yet.
# Usage: ensure_env <venv_dir> <extra> [<extra> ...]
ensure_env() {
    local venv_dir="$1"

    if [ "$USE_UV_FLAG" = true ] || [ ! -d "$venv_dir" ]; then
        setup_env "$@"
    fi
}
