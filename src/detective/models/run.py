import uuid
from django.db import models
from detective.models import Staging
from datetime import datetime, timezone

class Run(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_REQUIRES_ACTION = "requires_action"
    STATUS_CANCELLING = "cancelling"
    STATUS_CANCELLED = "cancelled"
    STATUS_FAILED = "failed"
    STATUS_COMPLETED = "completed"
    STATUS_EXPIRED = "expired"

    run_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_oa_id = models.CharField(max_length=255, unique=True)
    thread_oa_id = models.CharField(max_length=255, unique=True)
    staging = models.ForeignKey(Staging, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[
            (STATUS_QUEUED, "Queued"),
            (STATUS_IN_PROGRESS, "In Progress"),
            (STATUS_REQUIRES_ACTION, "Requires Action"),
            (STATUS_CANCELLING, "Cancelling"),
            (STATUS_CANCELLED, "Cancelled"),
            (STATUS_FAILED, "Failed"),
            (STATUS_COMPLETED, "Completed"),
            (STATUS_EXPIRED, "Expired"),
        ],
    )
    started_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Run ID: {self.id} - Thread ID: {self.thread_oa_id}"

    # Time until run was started (if in progress or queued)
    def get_elapsed_time(self):
        if self.status in [Run.STATUS_IN_PROGRESS, Run.STATUS_QUEUED]:
            current_time = datetime.now(timezone.utc)
            elapsed_time = current_time - self.date_modified
            return elapsed_time
        else:
            return None
