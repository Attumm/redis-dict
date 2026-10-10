#!/bin/bash
# Starts Valkey on port 6379 in Docker. Reuses the container if it already exists.
set -e

if docker container inspect my-valkey >/dev/null 2>&1; then
    docker start my-valkey
else
    docker run --name my-valkey -p 6379:6379 -d valkey/valkey
fi
