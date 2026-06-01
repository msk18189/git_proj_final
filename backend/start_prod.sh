#!/bin/bash

# Extract values from .env or use defaults
HOST=${API_HOST:-0.0.0.0}
PORT=${API_PORT:-8000}

# Calculate workers if not explicitly set
if [ -z "$API_WORKERS" ]; then
    CORES=$(nproc)
    WORKERS=$((CORES * 2 + 1))
else
    WORKERS=$API_WORKERS
fi

echo "Starting PRISM Backend in Production Mode using Gunicorn"
echo "Host: $HOST | Port: $PORT | Workers: $WORKERS"

gunicorn main:app \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind $HOST:$PORT \
    --log-level info \
    --timeout 120
