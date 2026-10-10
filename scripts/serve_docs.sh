#!/bin/bash
# Opens the built docs (run build_docs.sh first) in the default browser.
set -e
cd "$(dirname "$0")/.."

INDEX=docs/build/html/index.html
if [ ! -f "$INDEX" ]; then
    echo "$INDEX not found. Run scripts/build_docs.sh first."
    exit 1
fi

if command -v open >/dev/null 2>&1; then
    open "$INDEX"      # macOS
else
    xdg-open "$INDEX"  # Linux
fi
