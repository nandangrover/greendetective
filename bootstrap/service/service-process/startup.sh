#!/bin/bash
cd /var/www/green-detective

echo "Set up and start Celery worker and beat..."
# Conditionally start watchmedo based on TARGET_ENV

if [ "$TARGET_ENV" == "prd" ]; then
  echo "Running in production environment. Skipping watchmedo."
  celery -A green_detective worker -P gevent --beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info -Q gd_general,gd_scrape,gd_pre_staging,gd_post_staging
else
  echo "Running in non-production environment. Starting watchmedo..."
  watchmedo auto-restart --directory=./ --pattern=*.py --recursive -- celery -A green_detective worker --beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info -Q gd_general,gd_scrape,gd_pre_staging,gd_post_staging
fi
