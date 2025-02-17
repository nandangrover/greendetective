#!/bin/bash
cd /var/www/green-detective

echo "Creating Celery results tables..."
python manage.py migrate django_celery_results

echo "Start supervisord for Celery worker..."
exec supervisord --nodaemon --configuration /etc/supervisor/supervisord.conf
