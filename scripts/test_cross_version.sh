#!/bin/bash
set -e
cd "$(dirname "$0")/.."

source scripts/lib/env.sh
source scripts/lib/checks.sh

usage() {
    cat <<'EOF'
Usage: ./scripts/test_cross_version.sh [options] [<prev_ref> [<next_ref>]]

Run dynamic, property-based cross-version Redis database regression tests
between isolated virtual environments.

Options:
  --prev <spec>          Baseline version ref/tag/WORKTREE/pypi:<ver>
  --next <spec>          Target version ref/tag/WORKTREE/pypi:<ver>
  --pair <prev>:<next>   Explicit version pair (repeatable; use :: if spec contains ':')
  --forward-only         Run forward database upgrade checks only (skip rolling backward)
  --no-prereleases       Skip automatic latest-release -> unreleased pre-release pairs
  --examples <N>         Number of Hypothesis examples per property test (default: 15)
  --fetch-refs           Fetch tags, origin/main, and origin/v*-pre-release before running
  --use-uv <true|false>  Explicitly enable or disable uv
  --uv / --no-uv         Shorthand to enable or disable uv
  -h, --help             Show this help message
EOF
}

USE_UV_ARG=""
PREV_SPEC=""
NEXT_SPEC=""
PAIRS_JOINED=""
POSITIONAL=()
DO_FETCH=0

append_pair() {
    local raw="$1"
    local left right
    if [[ "$raw" == *"::"* ]]; then
        left="${raw%%::*}"
        right="${raw#*::}"
    elif [[ "$raw" == pypi:*:* ]]; then
        local rest="${raw#pypi:}"
        left="pypi:${rest%%:*}"
        right="${rest#*:}"
    elif [[ "$raw" == *":"* ]]; then
        left="${raw%%:*}"
        right="${raw#*:}"
    else
        echo "Invalid --pair value '$raw' (expected <prev>:<next> or <prev>::<next>)" >&2
        exit 2
    fi
    if [ -n "$PAIRS_JOINED" ]; then
        PAIRS_JOINED="${PAIRS_JOINED},,${left}::${right}"
    else
        PAIRS_JOINED="${left}::${right}"
    fi
}

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --prev)
            PREV_SPEC="$2"
            shift 2
            ;;
        --next)
            NEXT_SPEC="$2"
            shift 2
            ;;
        --pair)
            append_pair "$2"
            shift 2
            ;;
        --forward-only)
            export CROSS_VERSION_FORWARD_ONLY=1
            shift
            ;;
        --no-prereleases)
            export CROSS_VERSION_INCLUDE_PRERELEASES=0
            shift
            ;;
        --examples)
            export CROSS_VERSION_EXAMPLES="$2"
            shift 2
            ;;
        --fetch-refs)
            DO_FETCH=1
            shift
            ;;
        --use-uv)
            USE_UV_ARG="$2"
            shift 2
            ;;
        --uv)
            USE_UV_ARG="true"
            shift
            ;;
        --no-uv)
            USE_UV_ARG="false"
            shift
            ;;
        --)
            shift
            while [ $# -gt 0 ]; do
                POSITIONAL+=("$1")
                shift
            done
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

if [ "${#POSITIONAL[@]}" -gt 2 ]; then
    echo "Expected at most 2 positional arguments (<prev_ref> [<next_ref>]), got ${#POSITIONAL[@]}" >&2
    exit 2
fi

if [ "${#POSITIONAL[@]}" -ge 1 ] && [ -z "$PREV_SPEC" ]; then
    PREV_SPEC="${POSITIONAL[0]}"
fi
if [ "${#POSITIONAL[@]}" -eq 2 ] && [ -z "$NEXT_SPEC" ]; then
    NEXT_SPEC="${POSITIONAL[1]}"
fi

if [ "$DO_FETCH" -eq 1 ]; then
    git fetch origin --tags \
        "+refs/heads/main:refs/remotes/origin/main" \
        "+refs/heads/v*-pre-release:refs/remotes/origin/v*-pre-release"
fi

if [ -n "$PAIRS_JOINED" ]; then
    export CROSS_VERSION_PAIRS="$PAIRS_JOINED"
elif [ -n "$PREV_SPEC" ] || [ -n "$NEXT_SPEC" ]; then
    export PREV_REF="$PREV_SPEC"
    export NEXT_REF="${NEXT_SPEC:-WORKTREE}"
fi

resolve_use_uv "$USE_UV_ARG"
ensure_env .venv_dev dev

source .venv_dev/bin/activate

# Enforce full static-analysis & docstring gates on the regression suite itself
MYPY_PY_VER=$(python -c 'import sys; v = sys.version_info[:2]; print("3.10" if v >= (3, 10) else f"{v[0]}.{v[1]}")')
MYPYPATH="tests/regression:src" python -m mypy --strict --python-version "$MYPY_PY_VER" tests/regression/*.py
darglint tests/regression/
python -m pycodestyle --max-line-length=120 tests/regression
python -m pyflakes tests/regression
check_complexity tests/regression/*.py
bandit -q -r tests/regression
pydocstyle tests/regression/
PYTHONPATH="tests/regression:src" pylint -s n tests/regression/*.py

PYTHONPATH="tests/regression${PYTHONPATH:+:$PYTHONPATH}" \
    python -m unittest discover -s tests/regression -p 'tests_*.py' -v

deactivate
