#!/bin/bash
set -e

#!/bin/bash
set -e

if [ ! -d ".venv_dev" ]; then
    echo "Virtual environment not found. Running build script..."
    ./scripts/build_dev.sh
fi

source .venv_dev/bin/activate

# Type Check
python -m mypy

# Doctype Check
darglint src/redis_dict/

# Multiple linters
python -m pylama -i E501,E231 src

# Security Check
bandit -r src/redis_dict

# Docstring Check
pydocstyle src/redis_dict/

# Pylint
pylint src/

deactivate
