import random
import time
from celery import shared_task
from detective.utils import StatisticsProcessor, Assistant, start_processing_run
from detective.models import Run, Company, Report, Staging
import logging

logger = logging.getLogger(__name__)


@shared_task
def start_detective(company_id, report_uuid):
    logger.info("Starting detective")
    
    company = Company.objects.get(uuid=company_id)
    report = Report.objects.get(uuid=report_uuid)
    
    urls_to_process = report.urls if len(report.urls) > 0 else None
    
    # Scraper(company_id, company.domain, urls_to_process).start_scrapping()
    # StatisticsProcessor(company_id).process_raw_statistics()
    StatisticsProcessor(company_id).process_report()

    logger.info("Detective finished")


@shared_task
def trigger_assistant(staging_uuid):
    logger.info("Starting assistant")

    # check how many staging records are currently being processed

    processing_staging_records_count = Staging.objects.filter(
        processed=Staging.STATUS_PROCESSING
    ).count()
    
    staging = Staging.objects.get(uuid=staging_uuid)
    
    logger.info(f"Processing staging records: {processing_staging_records_count}")

    if processing_staging_records_count < 3 and staging.processed == Staging.STATUS_PENDING:
        try:
            staging.processed = Staging.STATUS_PROCESSING
            staging.save()
            
            Assistant(staging_uuid).trigger_run()
        except Exception as e:
            staging.processed = Staging.STATUS_FAILED
            staging.save()
            logger.error(f"Error while triggering assistant: {e}")
    elif staging.processed == Staging.STATUS_PENDING:
        logger.info("Too many staging records currently processing, waiting for some time")
        # check if the processing staging records have been stuck at processing for more than 5 minutes
        # if yes, then mark them as failed
        processing_staging_records = Staging.objects.filter(
            processed=Staging.STATUS_PROCESSING
        )
        
        for staging_record in processing_staging_records:
            if (time.time() - staging_record.updated_at.timestamp()) > 300:
                staging_record.processed = Staging.STATUS_FAILED
                staging_record.save()
        
        wait_time = random.randint(60, 120)
        trigger_assistant.apply_async(args=[staging_uuid], countdown=wait_time)

    logger.info("Assistant finished")
