from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

class ReportStorage(S3Boto3Storage):
    bucket_name = settings.REPORTS_BUCKET
    location = settings.REPORT_FILES_LOCATION
