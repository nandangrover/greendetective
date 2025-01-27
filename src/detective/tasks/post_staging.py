from celery import shared_task
from django.conf import settings
from detective.models import RawStatistics, Report
from detective.utils import StatisticsProcessor, Assistant
from typing import Optional
from datetime import datetime, timezone, timedelta
from django.db.models import Q
import logging
import traceback
import time
import random

logger = logging.getLogger(__name__)


@shared_task(
    queue=settings.CELERY_QUEUE_POST_STAGING, rate_limit=settings.CELERY_RATE_LIMIT_POST_STAGING
)
def trigger_statistic_assistant(stat_uuid: str) -> None:
    """
    Orchestrates the statistic assistant process for a statistic.
    """
    logger.info("Starting statistic assistant")

    # If raw statistic record is already processed, then skip
    stat = RawStatistics.objects.get(uuid=stat_uuid)
    if stat.processed == RawStatistics.STATUS_PROCESSED:
        logger.info("Raw statistic record already processed - skipping")
        return

    processing_stat_records_count = RawStatistics.objects.filter(
        processed=RawStatistics.STATUS_PROCESSING
    ).count()

    # Get progress percentage
    # Get the total number of raw statistics records for the company
    total_stat_records = RawStatistics.objects.filter(company_id=stat.company_id).count()

    # Get the number of raw statistics records that have been processed
    processed_stat_records = RawStatistics.objects.filter(
        company_id=stat.company_id, processed=RawStatistics.STATUS_PROCESSED
    ).count()

    progress_percentage = (processed_stat_records / total_stat_records) * 100

    logger.info(f"Progress percentage: {progress_percentage}")

    if processing_stat_records_count < 20 and stat.processed == RawStatistics.STATUS_PENDING:
        try:
            stat.processed = RawStatistics.STATUS_PROCESSING
            stat.save()

            # Get the first staging record associated with this statistic
            staging_record = stat.staging.first()
            if staging_record:
                Assistant(
                    staging_record.uuid, stat_uuid, Assistant.ASSISTANT_TYPE_POST
                ).trigger_statistic_run()
            else:
                logger.error("No staging record found for statistic")
                stat.processed = RawStatistics.STATUS_FAILED
                stat.save()
        except Exception:
            stat.processed = RawStatistics.STATUS_FAILED
            stat.save()
            logger.error(f"Error while triggering statistic assistant: {traceback.format_exc()}")

    elif stat.processed == RawStatistics.STATUS_PENDING:
        logger.info("Too many statistic records currently processing, waiting for some time")
        # check if the processing statistic records have been stuck at processing for more than 5 minutes
        # if yes, then mark them as failed
        processing_stat_records = RawStatistics.objects.filter(
            processed=RawStatistics.STATUS_PROCESSING
        )

        current_stat_restarted = False

        for stat_record in processing_stat_records:
            if (time.time() - stat_record.updated_at.timestamp()) > 300:
                stat_record.processed = RawStatistics.STATUS_PENDING
                stat_record.save()

                if stat_record.uuid == stat_uuid:
                    current_stat_restarted = True

                wait_time = random.randint(60, 120)
                trigger_statistic_assistant.apply_async(
                    args=[stat_record.uuid], countdown=wait_time
                )

        if not current_stat_restarted:
            trigger_statistic_assistant.apply_async(args=[stat_uuid], countdown=60)

    logger.info("Statistic assistant finished")


@shared_task
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
