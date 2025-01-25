import random
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from django.db.models import Q
from celery import shared_task, chord
from detective.utils import StatisticsProcessor, Scraper, Assistant, Completion
from detective.models import RawStatistics, Company, Report, Staging
import logging
from functools import partial

logger = logging.getLogger(__name__)


# TODO: Progress percentage all over
@shared_task
def start_detective(company_id: int, report_uuid: str) -> None:
    """
    Orchestrates the detective process for a company and a report.
    """
    logger.info("Starting detective")

    company = Company.objects.get(uuid=company_id)
    report = Report.objects.get(uuid=report_uuid)

    # Move the report to processing
    _move_report_to_processing(report)

    # Move all other reports for this company to cancelled
    _move_other_reports_to_cancelled(company_id, report_uuid)

    # Check if we need to skip scraping
    skip_scraping = _check_skip_scraping(company_id)

    # Scrape the domain if necessary
    _scrape_domain(company_id, company.domain, report, skip_scraping)

    # Process the URLs
    _process_urls(company_id, company, report)

    # Save company about section
    _save_company_about_section(company, report)

    # Process the report
    _process_report(company_id, company, report)

    logger.info("Detective finished")


def _move_report_to_processing(report: Report) -> None:
    """
    Moves the report to the processing state.
    """
    report.status = Report.STATUS_PROCESSING
    report.processed = False
    report.save()


def _move_other_reports_to_cancelled(company_id: int, report_uuid: str) -> None:
    """
    Moves all other reports for the company to the cancelled state.
    """
    Report.objects.filter(company_id=company_id, status=Report.STATUS_PENDING).exclude(
        uuid=report_uuid
    ).update(status=Report.STATUS_CANCELLED, processed=True)


def _check_skip_scraping(company_id: int) -> bool:
    """
    Checks if scraping should be skipped for the company.
    """
    # check if we have more than 10 records for the company, scraped less than a month ago
    staging_records = Staging.objects.filter(company_id=company_id).order_by("-created_at")

    skip_scraping = False

    if len(staging_records) > 10:
        last_staging_record = staging_records[0]
        last_staging_record_date = last_staging_record.created_at
        current_date = datetime.now(timezone.utc)
        if (current_date - last_staging_record_date).days < 30:
            logger.info("Company has been scraped less than a month ago, skipping")
            skip_scraping = True

    return skip_scraping


def _scrape_domain(company_id: int, domain: str, report: Report, skip_scraping: bool) -> None:
    """
    Scrapes the domain if necessary.
    """
    if not skip_scraping:
        Scraper(company_id, domain, urls_to_process=report.urls).crawl_domain_and_save()


def _process_urls(company_id: int, company: Company, report: Report) -> None:
    """
    Processes the URLs for the company and the report.
    """
    urls_to_process = report.urls if len(report.urls) > 0 else None

    # If urls_to_process is not empty, then mark all records apart from the ones in urls_to_process as defunct
    if urls_to_process:
        defunct_staging = Staging.objects.filter(company_id=company_id, defunct=False).exclude(
            url__in=urls_to_process
        )

        defunct_staging.update(defunct=True)

        # Mark all related raw statistics as defunct
        RawStatistics.objects.filter(staging__in=defunct_staging).update(defunct=True)

        # Only mark records as pending if they haven't been updated in the last hour
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        pending_staging = Staging.objects.filter(
            company_id=company_id,
            defunct=False,
            url__in=urls_to_process,
            updated_at__lt=one_day_ago,
        )

        if pending_staging.count() > 0:
            pending_staging.update(processed=Staging.STATUS_PENDING)

            # Delete all related raw statistics for which the staging record is marked as pending
            RawStatistics.objects.filter(staging__in=pending_staging).delete()
        else:
            logger.info("No pending staging records found")

    else:
        # Only mark records as pending if they haven't been updated in the last hour
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        pending_staging = Staging.objects.filter(
            company_id=company_id, updated_at__lt=one_day_ago
        )

        if pending_staging.count() > 0:
            pending_staging.update(processed=Staging.STATUS_PENDING, defunct=False)

            # Delete all related raw statistics for which the staging record is marked as pending
            RawStatistics.objects.filter(staging__in=pending_staging).delete()
        else:
            logger.info("No pending staging records found")


def _save_company_about_section(company: Company, report: Report) -> None:
    """
    Saves the company about section.
    """
    if not company.about_summary:
        about_raw = Scraper(company.id, company.domain).scrape_about_section()

        if about_raw:
            rule = f"Given the company name {company.name}, the about section was scraped from the company's domain {company.domain}. Summarized the about section to provide a brief overview of the company. Summary should be less than 300 characters."
            about_summary = Completion(about_raw, rule).create_completion()

            company.about_raw = about_raw
            company.about_summary = about_summary if about_summary else ""

            company.save()


def _process_report(company_id: int, company: Company, report: Report) -> None:
    """
    Processes the report for the company.
    """
    # Count of pending staging records
    pending_staging_count = Staging.objects.filter(
        company_id=company_id, defunct=False, processed=Staging.STATUS_PENDING
    ).count()

    if pending_staging_count == 0:
        logger.info("All raw statistics are processed - proceeding to next step")

        # Check if all statistics are processed
        pending_raw_stats_count = RawStatistics.objects.filter(
            company_id=company_id, defunct=False, processed=RawStatistics.STATUS_PENDING
        ).count()

        if pending_raw_stats_count == 0:
            logger.info(
                "All raw statistics are processed - proceeding to next step to create report"
            )
            StatisticsProcessor(company_id).process_report()
        else:
            logger.info("Raw statistics are still pending - skipping report creation")
            StatisticsProcessor(company_id).process_raw_statistics()
    else:
        logger.info("Creation of raw statistics started")
        StatisticsProcessor(company_id).create_raw_statistics()


@shared_task
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
        except Exception as e:
            stat.processed = RawStatistics.STATUS_FAILED
            stat.save()
            logger.error(f"Error while triggering statistic assistant: {e}")

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


@shared_task(bind=True)
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


@shared_task
def process_raw_statistics(company_id: int) -> None:
    """
    Process raw statistics for a company.
    """
    processor = StatisticsProcessor(company_id)
    processor.process_raw_statistics()


@shared_task
def check_staging_completion(company_id: int) -> None:
    """
    Check if all staging tasks are complete and trigger raw statistics processing.
    """
    logger.info("Checking staging completion")
    pending_count = (
        Staging.objects.filter(company_id=company_id, defunct=False)
        .filter(Q(processed=Staging.STATUS_PENDING) | Q(processed=Staging.STATUS_PROCESSING))
        .count()
    )

    if pending_count > 0:
        # Still have pending tasks, check again in 5 minutes
        check_staging_completion.apply_async(args=[company_id], countdown=300)
    else:
        # All tasks complete, trigger next phase
        process_raw_statistics.delay(company_id)

    logger.info("Staging completion check finished")


@shared_task
def check_statistics_completion(company_id: int) -> None:
    """
    Check if all statistics tasks are complete and trigger company statistics processing.
    """
    logger.info("Checking statistics completion")

    pending_count = (
        RawStatistics.objects.filter(company_id=company_id, defunct=False)
        .filter(
            Q(processed=RawStatistics.STATUS_PENDING)
            | Q(processed=RawStatistics.STATUS_PROCESSING)
        )
        .count()
    )

    if pending_count > 0:
        # Still have pending tasks, check again in 5 minutes
        check_statistics_completion.apply_async(args=[company_id], countdown=300)
    else:
        # All tasks complete, trigger final processing
        process_company_statistics.delay(company_id)

    logger.info("Statistics completion check finished")
