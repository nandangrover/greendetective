from celery import shared_task
from typing import Optional
from django.conf import settings
from detective.models import Staging, RawStatistics, Report
from detective.utils import Assistant
from datetime import datetime, timezone, timedelta
from django.db.models import Q
from detective.utils import StatisticsProcessor
import logging
import time
import random

logger = logging.getLogger(__name__)


@shared_task(
    queue=settings.CELERY_QUEUE_PRE_STAGING, rate_limit=settings.CELERY_RATE_LIMIT_PRE_STAGING
)
def process_company_statistics(company_id: int) -> Optional[bool]:
    """
    Process company statistics when all raw records are complete.
    Returns True if processing occurred, False if conditions not met, None on error.
    """
    try:
        # Check for any pending or processing records
        pending_count = (
            RawStatistics.objects.filter(company_id=company_id)
            .filter(
                Q(processed=RawStatistics.STATUS_PENDING)
                | Q(processed=RawStatistics.STATUS_PROCESSING)
            )
            .count()
        )

        if pending_count == 0:
            processor = StatisticsProcessor(company_id)
            processor.process_report()
            logger.info(f"Processed statistics for company {company_id}")
            return True
        else:
            # Check if any reports are stuck in processing
            stuck_reports = Report.objects.filter(
                company_id=company_id,
                status=Report.STATUS_PROCESSING,
                updated_at__lt=datetime.now(timezone.utc) - timedelta(minutes=30),
            )
            for report in stuck_reports:
                report.status = Report.STATUS_FAILED
                report.save()

            # rerun the task after 5 minutes
            process_company_statistics.apply_async(args=[company_id], countdown=300)

        logger.info(
            f"Skipped processing - {pending_count} records pending for company {company_id}"
        )
        return False

    except Exception as e:
        logger.error(f"Error processing statistics for company {company_id}: {str(e)}")
        # Update report status to failed on error
        Report.objects.filter(company_id=company_id, status=Report.STATUS_PROCESSING).update(
            status=Report.STATUS_FAILED
        )
        return None


@shared_task(
    queue=settings.CELERY_QUEUE_PRE_STAGING, rate_limit=settings.CELERY_RATE_LIMIT_PRE_STAGING
)
def process_raw_statistics(company_id: int) -> None:
    """
    Process raw statistics for a company.
    """
    processor = StatisticsProcessor(company_id)
    processor.process_raw_statistics()


@shared_task(
    queue=settings.CELERY_QUEUE_PRE_STAGING, rate_limit=settings.CELERY_RATE_LIMIT_PRE_STAGING
)
def trigger_staging_assistant(staging_uuid: str) -> None:
    """
    Orchestrates the staging assistant process for a staging record.
    """
    logger.info("Starting assistant for staging")

    # If staging record is already processed, then skip
    staging = Staging.objects.get(uuid=staging_uuid)
    if staging.processed == Staging.STATUS_PROCESSED:
        logger.info("Staging record already processed - skipping")
        return

    processing_staging_records_count = Staging.objects.filter(
        processed=Staging.STATUS_PROCESSING
    ).count()

    staging = Staging.objects.get(uuid=staging_uuid)

    # Get progress percentage
    # Get the total number of staging records for the company
    total_staging_records = Staging.objects.filter(company_id=staging.company_id).count()

    # Get the number of staging records that have been processed
    processed_staging_records = Staging.objects.filter(
        company_id=staging.company_id, processed=Staging.STATUS_PROCESSED
    ).count()

    progress_percentage = (processed_staging_records / total_staging_records) * 100

    logger.info(f"Progress percentage: {progress_percentage}")

    logger.info(f"Processing staging records count: {processing_staging_records_count}")

    if processing_staging_records_count < 20 and staging.processed == Staging.STATUS_PENDING:
        try:
            staging.processed = Staging.STATUS_PROCESSING
            staging.save()

            Assistant(staging_uuid, type=Assistant.ASSISTANT_TYPE_PRE).trigger_staging_run()
        except Exception as e:
            staging.processed = Staging.STATUS_FAILED
            staging.save()
            logger.error(f"Error while triggering assistant: {e}")
    elif staging.processed == Staging.STATUS_PENDING:
        logger.info("Too many staging records currently processing, waiting for some time")
        # check if the processing staging records have been stuck at processing for more than 5 minutes
        # if yes, then mark them as failed
        processing_staging_records = Staging.objects.filter(processed=Staging.STATUS_PROCESSING)

        current_staging_restarted = False

        for staging_record in processing_staging_records:
            if (time.time() - staging_record.updated_at.timestamp()) > 300:
                staging_record.processed = Staging.STATUS_PENDING
                staging_record.save()

                if staging_record.uuid == staging_uuid:
                    current_staging_restarted = True

                wait_time = random.randint(60, 120)
                trigger_staging_assistant.apply_async(
                    args=[staging_record.uuid], countdown=wait_time
                )

        if not current_staging_restarted:
            trigger_staging_assistant.apply_async(args=[staging_uuid], countdown=60)

    logger.info("Assistant for staging finished")
