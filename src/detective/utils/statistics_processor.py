import logging
from detective.models import RawStatistics, ProcessedStatistics, Staging


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

        for staging_uuid in staging_data:
            trigger_assistant.delay(staging_uuid)

    def process_statistics(self):
        # TODO: In the end, get all reports for this company with processing=True and add a s3 url for the generated report
        pass
