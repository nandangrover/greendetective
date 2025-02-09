#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting API service..."
# Add more debug output
echo "Environment variables:"
printenv

# Wait for the database to be ready
while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
  echo "Waiting for database to be ready..."
  sleep 2
done

# Install pgvector as a regular extension
echo "Installing pgvector extension..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Start the server
echo "Starting Gunicorn..."
exec gunicorn green_detective.wsgi:application --bind 0.0.0.0:8070 --workers 3 --log-level debug
