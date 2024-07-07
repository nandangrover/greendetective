from celery import shared_task
from detective.utils import StatisticsProcessor, Assistant, start_processing_run
from detective.models import Run
import logging

logger = logging.getLogger(__name__)


@shared_task
def start_detective(company_uuid):
    logger.info("Starting scrapper")
    
    # Scraper(company_uuid, start_url).crawl_domain_and_save()
    StatisticsProcessor(company_uuid).process_statistics()

    logger.info("Scrapper finished")


@shared_task
def trigger_assistant(staging_uuid):
    logger.info("Starting assistant")

    # check how many runs are currently running (status either in_progress or queued), if less than 5, start a new run, else wait for some time

    running_runs = Run.objects.filter(
        status__in=[Run.STATUS_IN_PROGRESS, Run.STATUS_QUEUED]
    ).count()

    if running_runs < 5:
        Assistant(staging_uuid).trigger_run()
    else:
        logger.info("Too many runs currently running, waiting for some time")
        # Create a new task to trigger the assistant after some time
        trigger_assistant.apply_async(args=[staging_uuid], countdown=60)

    logger.info("Assistant finished")
    
@shared_task
def process_run(staging_uuid, run_uuid):
    logger.info("Starting run")
    
    start_processing_run(staging_uuid, run_uuid)

    logger.info("Run finished")
