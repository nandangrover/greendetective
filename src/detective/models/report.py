import uuid
import os
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
from detective.models.company import Company
from custom_storages import ReportStorage


def get_upload_path(instance, filename):
    return os.path.join(f"company_{instance.company.uuid}", filename)


class Report(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    urls = ArrayField(
        models.URLField(max_length=2048), size=20, default=list, null=True, blank=True
    )
    processed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    report_file = models.FileField(
        storage=ReportStorage(), blank=True, null=True, upload_to=get_upload_path
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Report {self.uuid} for Company {self.company}"

    class Meta:
        db_table = "reports"
