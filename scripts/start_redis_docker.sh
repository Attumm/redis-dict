#!/bin/bash
# Starts Redis on port 6379 in Docker. Reuses the container if it already exists.
set -e

if docker container inspect my-redis >/dev/null 2>&1; then
    docker start my-redis
else
    docker run --name my-redis -p 6379:6379 -d redis
fi
