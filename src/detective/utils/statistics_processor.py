import logging
from detective.models import RawStatistics, ProcessedStatistics, Staging


class StatisticsProcessor:
    def __init__(self, company_uuid):
        self.logger = logging.getLogger(__name__)

        self.company_uuid = company_uuid

    def process_raw_statistics(self):
        from detective.tasks import trigger_assistant
        # get all staging uuids for a company from staging which have not been processed
        staging_data = Staging.objects.filter(company_uuid=self.company_uuid, processed=False).values_list('uuid', flat=True)
        
        for staging_uuid in staging_data:
            trigger_assistant.delay(staging_uuid)

    def process_statistics(self):
        # TODO: In the end, get all reports for this company with processing=True and add a s3 url for the generated report
        pass
