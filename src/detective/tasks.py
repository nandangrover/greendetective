from celery import shared_task
from detective.utils import StatisticsProcessor, Scraper, Assistant, start_processing_run
from detective.models import Run, Company, Report, Staging
import logging

logger = logging.getLogger(__name__)


@shared_task
def start_detective(company_id, report_uuid):
    logger.info("Starting detective")
    
    company = Company.objects.get(uuid=company_id)
    report = Report.objects.get(uuid=report_uuid)
    
    urls_to_process = report.urls if len(report.urls) > 0 else None
    
    Scraper(company_id, company.domain, urls_to_process).crawl_domain_and_save()
    # StatisticsProcessor(company_id).process_raw_statistics()

    logger.info("Detective finished")


@shared_task
def trigger_assistant(staging_uuid):
    logger.info("Starting assistant")

    # check how many staging records are currently being processed

    processing_staging_records = Staging.objects.filter(
        processed=Staging.STATUS_PROCESSING
    ).count()
    
    staging = Staging.objects.get(uuid=staging_uuid)

    if not processing_staging_records:
        try:
            staging.processed = Staging.STATUS_PROCESSING
            staging.save()
            
            Assistant(staging_uuid).trigger_run()
        except Exception as e:
            staging.processed = Staging.STATUS_FAILED
            staging.save()
            logger.error(f"Error while triggering assistant: {e}")
    else:
        logger.info("Too many staging records currently processing, waiting for some time")
        # Create a new task to trigger the assistant after some time
        trigger_assistant.apply_async(args=[staging_uuid], countdown=20)

    logger.info("Assistant finished")
    
@shared_task
def process_run(staging_uuid, run_uuid):
    logger.info("Starting run")
    
    start_processing_run(staging_uuid, run_uuid)

    logger.info("Run finished")
