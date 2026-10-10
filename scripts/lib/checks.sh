#!/bin/bash
# Shared checks, sourced by the scripts and the CI workflows.

# Fail when a function is more complex than the limit (10, the limit pylama used).
# mccabe's command line checks one file per call and always exits with 0,
# so this runs it per file and fails when it reports anything.
# Usage: check_complexity <file.py> [<file.py> ...]
check_complexity() {
    local max_complexity=10
    local failed=0
    local file output

    for file in "$@"; do
        output=$(python -m mccabe --min $((max_complexity + 1)) "$file")
        if [ -n "$output" ]; then
            echo "$file: too complex: $output"
            failed=1
        fi
    done

    return $failed
}
