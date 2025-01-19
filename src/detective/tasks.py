import random
import time
from datetime import datetime, timezone
from celery import shared_task
from detective.utils import (
    StatisticsProcessor,
    Scraper,
    Assistant,
    Completion,
    start_processing_run,
)
from detective.models import RawStatistics, Company, Report, Staging
import logging

logger = logging.getLogger(__name__)


# TODO: Progress percentage all over
@shared_task
def start_detective(company_id, report_uuid):
    logger.info("Starting detective")

    company = Company.objects.get(uuid=company_id)
    report = Report.objects.get(uuid=report_uuid)

    urls_to_process = report.urls if len(report.urls) > 0 else None

    # check if we have more than 10 records for the company, scraped less than a month ago, if yes, then don't start scraping
    staging_records = Staging.objects.filter(company_id=company_id).order_by(
        "-created_at"
    )

    skip_scraping = False

    if len(staging_records) > 10:
        last_staging_record = staging_records[0]
        last_staging_record_date = last_staging_record.created_at
        current_date = datetime.now(timezone.utc)
        if (current_date - last_staging_record_date).days < 30:
            logger.info("Company has been scraped less than a month ago, skipping")
            skip_scraping = True

    # Scraper(company_id, company.domain, urls_to_process).start_scrapping() if not skip_scraping else None
    (
        Scraper(company_id, company.domain).crawl_domain_and_save()
        if not skip_scraping
        else None
    )

    # Save company about section
    if not company.about_summary:
        about_raw = Scraper(company_id, company.domain).scrape_about_section()
        
        if about_raw:
            rule = f"Given the company name {company.name}, the about section was scraped from the company's domain {company.domain}. Summarized the about section to provide a brief overview of the company. Summary should be less than 300 characters."
            about_summary = Completion(about_raw, rule).create_completion()

            company.about_raw = about_raw
            company.about_summary = about_summary if about_summary else ""

            company.save()

    # StatisticsProcessor(company_id).create_raw_statistics()
    StatisticsProcessor(company_id).process_raw_statistics()
    StatisticsProcessor(company_id).process_report()

    # TODO: Send email to the user
    logger.info("Detective finished")
    
@shared_task
def trigger_statistic_assistant(stat_uuid):
    logger.info("Starting statistic assistant")

    stat = RawStatistics.objects.get(uuid=stat_uuid)
    
    processing_stat_records_count = RawStatistics.objects.filter(
        processed=RawStatistics.STATUS_PROCESSING
    ).count()
    
    # Get progress percentage
    # Get the total number of raw statistics records for the company
    total_stat_records = RawStatistics.objects.filter(
        company_id=stat.company_id
    ).count()
    
    # Get the number of raw statistics records that have been processed
    processed_stat_records = RawStatistics.objects.filter(
        company_id=stat.company_id, processed=RawStatistics.STATUS_PROCESSED
    ).count()
    
    progress_percentage = (processed_stat_records / total_stat_records) * 100
    
    logger.info(f"Progress percentage: {progress_percentage}")
    
    if (
        processing_stat_records_count < 5
        and stat.processed == RawStatistics.STATUS_PENDING
    ):
    
        try:
            stat.processed = RawStatistics.STATUS_PROCESSING
            stat.save()

            Assistant(stat.staging.uuid, stat_uuid, Assistant.ASSISTANT_TYPE_POST).trigger_statistic_run()
        except Exception as e:
            stat.processed = RawStatistics.STATUS_FAILED
            stat.save()
            logger.error(f"Error while triggering statistic assistant: {e}")
            
    elif stat.processed == RawStatistics.STATUS_PENDING:
        logger.info(
            "Too many statistic records currently processing, waiting for some time"
        )
        # check if the processing statistic records have been stuck at processing for more than 5 minutes
        # if yes, then mark them as failed
        processing_stat_records = RawStatistics.objects.filter(
            processed=RawStatistics.STATUS_PROCESSING
        )
        
        for stat_record in processing_stat_records: 
            if (time.time() - stat_record.updated_at.timestamp()) > 300:
                stat_record.processed = RawStatistics.STATUS_FAILED
                stat_record.save()
                
        wait_time = random.randint(60, 120)
        trigger_statistic_assistant.apply_async(args=[stat_uuid], countdown=wait_time)
              
    logger.info("Statistic assistant finished")


@shared_task
def trigger_staging_assistant(staging_uuid):
    logger.info("Starting assistant for staging")

    processing_staging_records_count = Staging.objects.filter(
        processed=Staging.STATUS_PROCESSING
    ).count()

    staging = Staging.objects.get(uuid=staging_uuid)

    # Get progress percentage
    # Get the total number of staging records for the company
    total_staging_records = Staging.objects.filter(
        company_id=staging.company_id
    ).count()

    # Get the number of staging records that have been processed
    processed_staging_records = Staging.objects.filter(
        company_id=staging.company_id, processed=Staging.STATUS_PROCESSED
    ).count()

    progress_percentage = (processed_staging_records / total_staging_records) * 100

    logger.info(f"Progress percentage: {progress_percentage}")
    
    logger.info(f"Processing staging records count: {processing_staging_records_count}")

    if (
        processing_staging_records_count < 5
        and staging.processed == Staging.STATUS_PENDING
    ):
        try:
            staging.processed = Staging.STATUS_PROCESSING
            staging.save()

            Assistant(staging_uuid).trigger_staging_run()
        except Exception as e:
            staging.processed = Staging.STATUS_FAILED
            staging.save()
            logger.error(f"Error while triggering assistant: {e}")
    elif staging.processed == Staging.STATUS_PENDING:
        logger.info(
            "Too many staging records currently processing, waiting for some time"
        )
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
        trigger_staging_assistant.apply_async(args=[staging_uuid], countdown=wait_time)

    logger.info("Assistant for staging finished")
