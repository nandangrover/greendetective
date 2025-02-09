#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting API service..."
# Add more debug output
echo "Environment variables:"
printenv

# Wait for database to be ready using a simple loop
echo "Waiting for database..."
counter=0
until python manage.py check --database default; do
    counter=$((counter+1))
    if [ $counter -gt 60 ]; then
        echo "Database connection timed out!"
        exit 1
    fi
    echo "Database not ready yet. Waiting..."
    sleep 1
done

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Start the server
echo "Starting Gunicorn..."
exec gunicorn green_detective.wsgi:application --bind 0.0.0.0:8070 --workers 3 --log-level debug
