from celery import shared_task
from detective.utils import StatisticsProcessor, Assistant, start_processing_run
from detective.models import Run, Company, Report
import logging

logger = logging.getLogger(__name__)


@shared_task
def start_detective(company_uuid, report_uuid):
    logger.info("Starting scrapper")
    
    company = Company.objects.get(uuid=company_uuid)
    report = Report.objects.get(uuid=report_uuid)
    
    urls_to_process = report.urls if len(report.urls) > 0 else None
    
    # Scraper(company_uuid, company.domain, urls_to_process).start_scrapping()
    StatisticsProcessor(company_uuid).process_raw_statistics()

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
