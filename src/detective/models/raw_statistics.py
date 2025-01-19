from django.db import models
from detective.models import Company, Staging
import uuid


class RawStatistics(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_PROCESSED = "PROCESSED"
    STATUS_FAILED = "FAILED"
    
    PROCESSED_STATUSES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
    ]
    
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, default=None)
    staging = models.OneToOneField(Staging, on_delete=models.DO_NOTHING, default=None, unique=True)
    claim = models.TextField(default=None)
    evaluation = models.TextField()
    score = models.FloatField()
    processed = models.CharField(max_length=255, choices=PROCESSED_STATUSES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    defunct = models.BooleanField(default=False)

    def __str__(self):
        return f"Raw Statistics {self.uuid}"
