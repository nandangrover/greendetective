#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting API service..."
# Add more debug output
echo "Environment variables:"
printenv

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Create superuser
python manage.py ensure_adminuser --noinput

# Start the server
# Run Gunicorn command with specified configurations
gunicorn green_detective.wsgi -c ${BOOTSTRAP_DIR}/service/service-api/gunicorn-config.py ${GUNICORN_ARGS}

exec "$@"
