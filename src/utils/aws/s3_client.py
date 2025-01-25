import os
from typing import Optional
from django.conf import settings
import boto3
from utils.datatypes import is_file_field_empty, merge_dict


class S3Client:
    def __init__(self):
        client_fe_params = {}
        client_params = {}
        if os.environ.get("AWS_S3_ENDPOINT_URL_FE", None) is not None:
            client_fe_params["endpoint_url"] = os.environ.get("AWS_S3_ENDPOINT_URL_FE")

        if os.environ.get("AWS_S3_ENDPOINT_URL", None) is not None:
            client_params["endpoint_url"] = os.environ.get("AWS_S3_ENDPOINT_URL")

        self.client_fe = boto3.client("s3", **client_fe_params)
        self.client = boto3.client("s3", **client_params)
        self.resource = boto3.resource("s3", **client_params)
        self.bulk_client = boto3.client(
            "s3",
            **merge_dict(
                client_fe_params,
                {"config": boto3.session.Config(s3={"addressing_style": "path"})},
            ),
        )

    def get_report_url(self, report, expires_in=None):
        expires_in = expires_in or settings.AWS_S3_EXPIRES_IN_REPORT_URL
        url = self.client_fe.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.REPORTS_BUCKET, "Key": "reports/" + report},
            ExpiresIn=expires_in,
        )
        return url
