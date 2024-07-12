import logging
import pandas as pd
from detective.models import Report
from datetime import datetime
from detective.models import RawStatistics, ProcessedStatistics, Staging
from django.db.models import Avg, StdDev
from tailslide import Median, Percentile


class StatisticsProcessor:
    def __init__(self, company_id):
        self.logger = logging.getLogger(__name__)

        self.company_id = company_id

    def process_raw_statistics(self):
        from detective.tasks import trigger_assistant

        # get all staging uuids for a company from staging which have not been processed
        staging_data = Staging.objects.filter(
            company_id=self.company_id, processed=Staging.STATUS_PENDING
        ).values_list("uuid", flat=True)

        wait_time = 0
        for staging_uuid in staging_data:
            # Increase wait time for each staging record
            wait_time += 10
            trigger_assistant.apply_async(args=[staging_uuid], countdown=wait_time)

    def process_report(self):
        # TODO: In the end, get all reports for this company with processing=True and add a s3 url for the generated report

        # Mean score, median score, and standard deviation of the scores
        mean = RawStatistics.objects.filter(company_id=self.company_id).aggregate(
            Avg("score")
        )["score__avg"]
        median = RawStatistics.objects.filter(company_id=self.company_id).aggregate(
            Median("score")
        )["score__median"]
        std_dev = RawStatistics.objects.filter(company_id=self.company_id).aggregate(
            StdDev("score")
        )["score__stddev"]
        percentile = RawStatistics.objects.filter(company_id=self.company_id).aggregate(
            Percentile("score", 0.9)
        )["score__percentile"]

        print(
            f"Mean: {mean}, Median: {median}, Std Dev: {std_dev}, 90th Percentile: {percentile}"
        )

        company_stats = RawStatistics.objects.filter(
            company_id=self.company_id
        ).order_by("-score")

        # Create a pandas dataframe with the above statistics
        stats = {
            "Mean": mean,
            "Median": median,
            "Standard Deviation": std_dev,
            "90th Percentile": percentile,
        }

        # get score, claim, and evaluation for each record
        scores = [stat.score for stat in company_stats]
        claims = [stat.claim for stat in company_stats]
        evaluations = [stat.evaluation for stat in company_stats]
        urls = [stat.staging.url for stat in company_stats]
        stat_processed_date = [
            datetime.strftime(stat.created_at, "%Y-%m-%d %H:%M:%S")
            for stat in company_stats
        ]

        # create a pandas dataframe with the above arrays
        data = {
            "Score": scores,
            "Claim": claims,
            "Evaluation": evaluations,
            "URL": urls,
            "Processed Date": stat_processed_date,
        }

        df = pd.DataFrame(data)

        # company_name
        company_name = company_stats[0].company.name

        file_name = (
            f"{company_name}_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
        )

        self.convert_to_excel(company_name, file_name, stats, df)
        # find report for this company with processing=True
        report = Report.objects.filter(
            company_id=self.company_id, processing=True
        ).first()

        report.report_file.save(file_name, open(file_name, "rb"))

    def convert_to_excel(self, company_name, filename, stats, df):
        with pd.ExcelWriter(filename) as writer:
            df.to_excel(
                writer, startrow=12, startcol=0, sheet_name="green_washing", index=False
            )

            worksheet = writer.sheets["green_washing"]
            workbook = writer.book

            first_row_format = workbook.add_format(
                {"bold": True, "text_wrap": True, "font_size": 14}
            )

            heading_format = workbook.add_format(
                {"bold": True, "text_wrap": True, "font_size": 12}
            )

            first_row_format.set_align("left")
            # first_row_format.set_align("vcenter")

            standard_format = workbook.add_format(
                {"text_wrap": True, "bold": True, "text_wrap": True}
            )
            standard_format.set_align("left")
            # standard_format.set_align("vcenter")

            worksheet.merge_range(
                0,
                0,
                0,
                2,
                f"Greenwashing Report - for {company_name}",
                first_row_format,
            )
            worksheet.merge_range(
                2,
                0,
                2,
                2,
                f"Statistics",
                heading_format,
            )

            worksheet.merge_range(
                3,
                0,
                3,
                2,
                f"Mean - {stats['Mean']}",
                standard_format,
            )
            worksheet.merge_range(
                4,
                0,
                4,
                2,
                f"Median - {stats['Median']}",
                standard_format,
            )
            # N/A if all categories are included
            worksheet.merge_range(
                5,
                0,
                5,
                2,
                f"Standard Deviation - {stats['Standard Deviation']}",
                standard_format,
            )

            worksheet.merge_range(
                6,
                0,
                6,
                2,
                f"90th Percentile - {stats['90th Percentile']}",
                standard_format,
            )

            worksheet.merge_range(
                7,
                0,
                7,
                2,
                f"Greenwashing Scale:",
                heading_format,
            )

            worksheet.merge_range(
                8,
                0,
                8,
                2,
                f"1 - 3: Low Greenwashing | 4 - 6: Moderate Greenwashing | 7 - 10: High Greenwashing",
                standard_format,
            )

            for column in df:
                max_length = (
                    df[column]
                    .apply(lambda x: len(str(x) if x is not None else ""))
                    .max()
                )
                column_length = max(
                    max_length, len(str(column) if column is not None else "")
                )
                col_idx = df.columns.get_loc(column)
                writer.sheets["green_washing"].set_column(
                    col_idx, col_idx, column_length
                )

            worksheet.set_column(0, 0, 15)
