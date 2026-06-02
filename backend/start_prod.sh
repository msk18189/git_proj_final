#!/bin/bash

# SECURITY: Bind to 127.0.0.1 (localhost) by default.
# Nginx (or another reverse proxy) MUST sit in front to handle TLS + public traffic.
# Never expose gunicorn directly on 0.0.0.0 in production.
HOST=${API_HOST:-127.0.0.1}
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
echo "NOTE: Ensure Nginx is proxying HTTPS traffic to $HOST:$PORT"

gunicorn main:app \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind $HOST:$PORT \
    --log-level info \
    --timeout 120 \
    --forwarded-allow-ips "127.0.0.1"
