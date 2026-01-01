#!/bin/bash
# Entrypoint script for secops_api container

set -e

echo "Starting SecOps API container..."

# Configure system
dpkg --configure -a || true

# Install build dependencies if needed
if ! command -v gcc >/dev/null 2>&1; then
    echo "Installing build dependencies..."
    apt-get update && apt-get install -y --no-install-recommends gcc build-essential python3-dev
fi

# Install Python dependencies if needed
if ! python -c 'import openstack,fastapi,uvicorn,apscheduler,prometheus_client' >/dev/null 2>&1; then
    echo "Installing Python dependencies..."
    pip install --no-cache-dir -r requirements.txt
fi

# Load OpenStack environment variables
if [ -f /app/openstack.env ]; then
    echo "Loading OpenStack environment variables..."
    set -a
    source /app/openstack.env
    set +a
    echo "OS_AUTH_URL=${OS_AUTH_URL:-not set}"
    echo "OS_PROJECT_NAME=${OS_PROJECT_NAME:-not set}"
else
    echo "Warning: /app/openstack.env not found"
fi

# Start the application
echo "Starting uvicorn server..."
exec uvicorn app:app --host 0.0.0.0 --port 8000







