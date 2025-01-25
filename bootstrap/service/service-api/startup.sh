#!/bin/sh
set -e
python manage.py collectstatic --noinput
# python manage.py migrate --noinput
# # Create superuser
# python manage.py ensure_adminuser --noinput

# Run Gunicorn command with specified configurations
gunicorn green_detective.wsgi -c ${BOOTSTRAP_DIR}/service/service-api/gunicorn-config.py ${GUNICORN_ARGS}

exec "$@"
