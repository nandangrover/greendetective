from detective.models import Report, Company, RawStatistics, Staging
from detective.utils import StatisticsProcessor, Scraper, Assistant, Completion
from detective.tasks.scraping import crawl_domain, scrape_single_url
from datetime import datetime, timezone, timedelta
import logging
from celery import chord

logger = logging.getLogger(__name__)


def move_report_to_processing(report: Report) -> None:
    """
    Moves the report to the processing state.
    """
    report.status = Report.STATUS_PROCESSING
    report.processed = False
    report.save()


def move_other_reports_to_cancelled(company_id: int, report_uuid: str) -> None:
    """
    Moves all other reports for the company to the cancelled state.
    """
    Report.objects.filter(company_id=company_id, status=Report.STATUS_PENDING).exclude(
        uuid=report_uuid
    ).update(status=Report.STATUS_CANCELLED, processed=True)


def check_skip_scraping(company_id: int) -> bool:
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


def scrape_domain(company_id: int, domain: str, report: Report, skip_scraping: bool) -> None:
    """
    Scrapes the domain if necessary. Uses a chord to ensure all scraping completes before proceeding.
    """
    from detective.tasks.general import process_after_scraping

    if not skip_scraping:
        scraping_tasks = []
        if report.urls and len(report.urls) > 0:
            # If specific URLs are provided, process them directly
            for url in report.urls:
                scraping_tasks.append(scrape_single_url.s(company_id, url))
        else:
            # Otherwise, start a full domain crawl which will generate its own tasks
            scraping_tasks.append(crawl_domain.s(company_id, domain))

        if scraping_tasks:
            # Create a chord - after all scraping tasks complete, call process_after_scraping
            # Use .si() to ignore the results from the chord header
            chord(scraping_tasks)(process_after_scraping.si(company_id, report.uuid))


def process_urls(company_id: int, company: Company, report: Report) -> None:
    """
    Processes the URLs for the company and the report.
    """

    urls_to_process = report.urls if report.urls and len(report.urls) > 0 else None

    # If urls_to_process is not empty, then mark all records apart from the ones in urls_to_process as defunct
    if urls_to_process:
        defunct_staging = Staging.objects.filter(company_id=company_id, defunct=False).exclude(
            url__in=urls_to_process
        )

        defunct_staging.update(defunct=True)

        # Mark all related raw statistics as defunct
        RawStatistics.objects.filter(staging__in=defunct_staging).update(defunct=True)

        # Only mark records as pending if they haven't been updated in the last day
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


def save_company_about_section(company: Company, report: Report) -> None:
    """
    Saves the company about section.
    """
    if not company.about_summary:
        about_raw = Scraper(company.uuid, company.domain).scrape_about_section()

        if about_raw:
            rule = f"Given the company name {company.name}, the about section was scraped from the company's domain {company.domain}. Summarized the about section to provide a brief overview of the company. Summary should be less than 300 characters."
            about_summary = Completion(about_raw, rule).create_completion()

            company.about_raw = about_raw
            company.about_summary = about_summary if about_summary else ""

            company.save()


def process_report(company_id: int, company: Company, report: Report) -> None:
    """
    Processes the report for the company.
    """
    # Only start processing if there are no pending staging records
    pending_staging_count = Staging.objects.filter(
        company_id=company_id, defunct=False, processed=Staging.STATUS_PENDING
    ).count()

    if pending_staging_count == 0:
        logger.info("All staging records are processed - proceeding to next step")

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
