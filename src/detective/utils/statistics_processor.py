import logging
import os
import pandas as pd
from detective.models import Report
from datetime import datetime
from detective.models import Company, RawStatistics, Staging
from django.db.models import Avg, StdDev
from tailslide import Median, Percentile
from celery import group
from typing import Optional, Tuple
from detective.utils.report_generator import ReportGenerator


logger = logging.getLogger(__name__)


class StatisticsProcessor:
    def __init__(self, company_id: int) -> None:
        """
        Initializes the StatisticsProcessor with the given company_id.
        """
        self.logger = logging.getLogger(__name__)

        self.company_id = company_id

    def create_raw_statistics(self) -> None:
        """
        Creates raw statistics for the company.
        """
        from detective.tasks import trigger_staging_assistant, check_staging_completion

        # get all staging uuids for a company from staging which have not been processed
        staging_data = Staging.objects.filter(
            company_id=self.company_id, processed=Staging.STATUS_PENDING, defunct=False
        ).values_list("uuid", flat=True)

        # Create a list of tasks with staggered delays
        tasks = []
        wait_time = 0
        for staging_uuid in staging_data:
            tasks.append(trigger_staging_assistant.s(staging_uuid).set(countdown=wait_time))
            wait_time += 10

        # Instead of chord, use group and schedule a separate completion check
        if tasks:
            logger.info("Raw statistics processing started")
            logger.info(f"Processing raw statistics for company {self.company_id}")
            group(tasks).apply_async()
            # Schedule completion check task
            check_staging_completion.apply_async(
                args=[self.company_id],
                countdown=wait_time + 5,  # Start checking 5 minutes after last task
            )

    def process_raw_statistics(self) -> None:
        """
        Processes raw statistics for the company.
        """
        from detective.tasks import (
            trigger_statistic_assistant,
            check_statistics_completion,
        )

        raw_statistics = RawStatistics.objects.filter(
            company_id=self.company_id,
            defunct=False,
            processed=RawStatistics.STATUS_PENDING,
        ).values_list("uuid", flat=True)

        tasks = []
        wait_time = 0
        for stat_uuid in raw_statistics:
            tasks.append(trigger_statistic_assistant.s(stat_uuid).set(countdown=wait_time))
            wait_time += 10

        if tasks:
            logger.info("Processing raw statistics started")
            logger.info(f"Processing company statistics for company {self.company_id}")
            group(tasks).apply_async()
            # Schedule completion check task
            check_statistics_completion.apply_async(
                args=[self.company_id],
                countdown=wait_time + 5,  # Start checking 5 minutes after last task
            )

    def process_report(self) -> None:
        """
        Processes the report for the company.
        """
        logger.info(f"Processing report for company {self.company_id}")
        try:
            stats, df = ReportGenerator.process_report_data(self.company_id)

            company = Company.objects.get(uuid=self.company_id)
            company_name = company.name

            file_name = (
                f"{company_name}_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
            )

            report_generator = ReportGenerator(company_name, file_name, stats, df)
            report_generator.generate()
            # find report for this company with status=processing and latest
            report = (
                Report.objects.filter(
                    company_id=self.company_id,
                    status=Report.STATUS_PROCESSING,
                )
                .order_by("-created_at")
                .first()
            )

            report.report_file.save(file_name, open(file_name, "rb"))
            report.status = Report.STATUS_PROCESSED
            report.processed = True  # For backwards compatibility
            report.save()

            logger.info(f"Report for company {self.company_id} created")
            os.remove(file_name)
        except Exception as e:
            logger.error(f"Error processing report: {str(e)}")
            Report.objects.filter(
                company_id=self.company_id, status=Report.STATUS_PROCESSING
            ).update(status=Report.STATUS_FAILED)
            raise
