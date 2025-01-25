import logging
import time
from django.conf import settings
from detective.models import Run, Staging, RawStatistics

logger = logging.getLogger(__name__)

POLLING_MAX_SECONDS = 300
POLL_INTERVAL = 2


class BaseRunProcessor:
    def __init__(self, staging_uuid, run_uuid, stat_uuid=None):
        self.staging_uuid = staging_uuid
        self.run_uuid = run_uuid
        self.stat_uuid = stat_uuid

    def start_processing(self):
        """Process run for a thread."""
        try:
            self._start_polling(0)
        except Exception as e:
            run = Run.objects.get(run_uuid=self.run_uuid)
            self._save_run_status(run, Run.STATUS_FAILED)
            self._handle_failure()
            logger.error(
                f"Error while processing run for staging record: {self.staging_uuid}, run: {self.run_uuid}"
            )
            logger.error(e)

    def _start_polling(self, elapsed_time=0):
        """Start polling for run status."""
        from detective.utils import Assistant

        if elapsed_time > POLLING_MAX_SECONDS:
            logger.error(f"Run processing timed out for run: {self.run_uuid}")
            run_instance = Run.objects.get(run_uuid=self.run_uuid)
            self._save_run_status(run_instance, Run.STATUS_FAILED)
            return

        run_instance = Run.objects.get(run_uuid=self.run_uuid)
        logger.info(
            f"Processing run for thread: {run_instance.thread_oa_id}, run: {run_instance.run_oa_id}"
        )

        thread_oa_id = run_instance.thread_oa_id
        run_oa_id = run_instance.run_oa_id

        assistant = Assistant(self.staging_uuid)
        run_openai = assistant.retrieve_run(thread_oa_id, run_oa_id)

        status = run_openai.status
        if status in [Run.STATUS_IN_PROGRESS, Run.STATUS_QUEUED]:
            time.sleep(POLL_INTERVAL)
            elapsed_time += POLL_INTERVAL
            self._start_polling(elapsed_time)

        elif status == Run.STATUS_COMPLETED:
            steps = assistant.list_run_steps(thread_oa_id, run_oa_id)
            self._process_run_steps(assistant, thread_oa_id, steps)
            self._save_run_status(run_instance, Run.STATUS_COMPLETED)

        elif status in [Run.STATUS_FAILED, Run.STATUS_CANCELLED, Run.STATUS_EXPIRED]:
            self._handle_failure()
            self._save_run_status(run_instance, status)

        else:
            self._handle_failure()
            self._save_run_status(run_instance, Run.STATUS_FAILED)

    def _process_run_steps(self, assistant, thread_oa_id, steps):
        """Abstract method to be implemented by subclasses"""
        raise NotImplementedError

    def _handle_failure(self):
        """Abstract method to be implemented by subclasses"""
        raise NotImplementedError

    @staticmethod
    def _save_run_status(run, status):
        run.status = status
        run.save()

    @staticmethod
    def _save_statistic_status(stat_uuid, status):
        try:
            raw_statistic = RawStatistics.objects.get(uuid=stat_uuid)
            raw_statistic.processed = status
            raw_statistic.save()
        except Exception as e:
            print(f"Error saving statistic status: {e}")
            raise

    @staticmethod
    def _save_staging_status(staging_uuid, status):
        try:
            staging = Staging.objects.get(uuid=staging_uuid)
            staging.processed = status
            staging.save()
        except Exception as e:
            print(f"Error saving staging status: {e}")
            raise
