import os
from celery import Celery
from logging import getLogger
from django.db import connections


logger = getLogger(__name__)

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "green_detective.settings")

app = Celery("green_detective")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


def check_db_connection():
    try:
        db_connection = connections["default"]
        c = db_connection.cursor()
        c.execute("SELECT 1")
        c.fetchone()
        logger.info("Database connection is working")
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    logger.info(f"Request: {self.request!r}")
    check_db_connection()
