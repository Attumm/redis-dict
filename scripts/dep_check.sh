#!/bin/bash
set -e

ENVIRONMENTS=$(python -c 'import tomli; data=tomli.load(open("pyproject.toml", "rb")); envs=[env for env in data["project"]["optional-dependencies"].keys() if env != "safety"]; print("prod " + " ".join(envs))')

# Create reports directory
mkdir -p reports

for ENV_NAME in $ENVIRONMENTS; do
    echo "Analyzing ${ENV_NAME} environment..."

    # Setup clean venv
    if [ -d ".venv_${ENV_NAME}" ]; then
       rm -rf .venv_${ENV_NAME}
    fi

    python3 -m venv .venv_${ENV_NAME}
    source .venv_${ENV_NAME}/bin/activate
    pip install --upgrade pip


    if [ "$ENV_NAME" = "prod" ]; then
        pip install -e ".[safety]"
    else
        pip install -e ".[safety, $ENV_NAME]"
    fi

    # Generate reports
    echo "Environment: ${ENV_NAME}" > reports/${ENV_NAME}_report.txt
    echo "===================" >> reports/${ENV_NAME}_report.txt

    echo "\nPip Compile Output:" >> reports/${ENV_NAME}_report.txt
    pip-compile --output-file=- >> reports/${ENV_NAME}_report.txt

    echo "\nSafety Check:" >> reports/${ENV_NAME}_report.txt
    safety scan >> reports/${ENV_NAME}_report.txt

    deactivate
done
