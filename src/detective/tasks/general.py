from celery import shared_task
from django.conf import settings
from detective.models import Report, Company, RawStatistics, Staging
from .helpers import (
    move_report_to_processing,
    move_other_reports_to_cancelled,
    check_skip_scraping,
    scrape_domain,
    process_urls,
    save_company_about_section,
    process_report,
)
from .post_staging import process_company_statistics
from .pre_staging import process_raw_statistics
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


@shared_task(queue=settings.CELERY_QUEUE_GENERAL)
def process_after_scraping(company_id: int, report_uuid: str) -> None:
    """
    Called after all scraping tasks complete. Continues the processing pipeline.
    """
    logger.info("All scraping tasks completed - continuing processing")

    try:
        company = Company.objects.get(uuid=company_id)
        report = Report.objects.get(uuid=report_uuid)

        # Process URLs and continue with the pipeline
        try:
            process_urls(company_id, company, report)
        except Exception as e:
            logger.error(f"Error in process_urls: {str(e)}", exc_info=True)
            raise

        try:
            save_company_about_section(company, report)
        except Exception as e:
            logger.error(f"Error in save_company_about_section: {str(e)}", exc_info=True)
            raise

        try:
            process_report(company_id, company, report)
        except Exception as e:
            logger.error(f"Error in process_report: {str(e)}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"Error in post-scraping processing: {str(e)}", exc_info=True)
        # Update report status to failed on error
        Report.objects.filter(uuid=report_uuid).update(status=Report.STATUS_FAILED)


@shared_task(queue=settings.CELERY_QUEUE_GENERAL, rate_limit=settings.CELERY_RATE_LIMIT_GENERAL)
def start_detective(company_id: int, report_uuid: str) -> None:
    """
    Orchestrates the detective process for a company and a report.
    """
    logger.info("Starting detective")

    company = Company.objects.get(uuid=company_id)
    report = Report.objects.get(uuid=report_uuid)

    # Move the report to processing
    move_report_to_processing(report)

    # Move all other reports for this company to cancelled
    move_other_reports_to_cancelled(company_id, report_uuid)

    # Check if we need to skip scraping
    skip_scraping = check_skip_scraping(company_id)

    # Scrape the domain if necessary - this now handles task orchestration with chord
    scrape_domain(company_id, company.domain, report, skip_scraping)

    if skip_scraping:
        # If skipping scraping, proceed directly to processing
        process_urls(company_id, company, report)
        save_company_about_section(company, report)
        process_report(company_id, company, report)

    logger.info("Detective started")


@shared_task(queue=settings.CELERY_QUEUE_GENERAL, rate_limit=settings.CELERY_RATE_LIMIT_GENERAL)
def check_staging_completion(company_id: int) -> None:
    """
    Check if all staging tasks are complete and trigger raw statistics processing.
    After 2 retries, restarts the entire detective process.
    """
    logger.info("Checking staging completion")

    # Get retry count from task request
    retries = (
        check_staging_completion.request.retries
        if hasattr(check_staging_completion.request, "retries")
        else 0
    )

    pending_count = (
        Staging.objects.filter(company_id=company_id, defunct=False)
        .filter(Q(processed=Staging.STATUS_PENDING) | Q(processed=Staging.STATUS_PROCESSING))
        .count()
    )

    if pending_count > 0:
        if retries >= 2:
            # After 2 retries, restart the entire process
            logger.warning(
                f"Staging completion check failed after {retries} retries. Restarting detective process."
            )
            report = Report.objects.filter(company_id=company_id).latest("created_at")
            start_detective.delay(company_id, str(report.uuid))
        else:
            # Still have pending tasks, check again in 5 minutes
            check_staging_completion.apply_async(
                args=[company_id], countdown=300, retries=retries + 1
            )
    else:
        # All tasks complete, trigger next phase
        process_raw_statistics.delay(company_id)

    logger.info("Staging completion check finished")


@shared_task(queue=settings.CELERY_QUEUE_GENERAL, rate_limit=settings.CELERY_RATE_LIMIT_GENERAL)
def check_statistics_completion(company_id: int) -> None:
    """
    Check if all statistics tasks are complete and trigger company statistics processing.
    After 2 retries, restarts the entire detective process.
    """
    logger.info("Checking statistics completion")

    # Get retry count from task request
    retries = (
        check_statistics_completion.request.retries
        if hasattr(check_statistics_completion.request, "retries")
        else 0
    )

    pending_count = (
        RawStatistics.objects.filter(company_id=company_id, defunct=False)
        .filter(
            Q(processed=RawStatistics.STATUS_PENDING)
            | Q(processed=RawStatistics.STATUS_PROCESSING)
        )
        .count()
    )

    if pending_count > 0:
        if retries >= 2:
            # After 2 retries, restart the entire process
            logger.warning(
                f"Statistics completion check failed after {retries} retries. Restarting detective process."
            )
            report = Report.objects.filter(company_id=company_id).latest("created_at")
            start_detective.delay(company_id, str(report.uuid))
        else:
            # Still have pending tasks, check again in 5 minutes
            check_statistics_completion.apply_async(
                args=[company_id], countdown=300, retries=retries + 1
            )
    else:
        # All tasks complete, trigger final processing
        process_company_statistics.delay(company_id)

    logger.info("Statistics completion check finished")
