#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting API service..."
# Add more debug output
echo "Environment variables:"
printenv

# Wait for database to be ready
echo "Waiting for database..."
python manage.py wait_for_db --timeout=60

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Start the server
echo "Starting Gunicorn..."
exec gunicorn green_detective.wsgi:application --bind 0.0.0.0:8070 --workers 3 --log-level debug
