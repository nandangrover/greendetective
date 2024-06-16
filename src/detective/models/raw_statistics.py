from django.db import models
import uuid


class RawStatistics(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(max_length=2048)
    evaluation = models.TextField()
    score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    defunct = models.BooleanField(default=False)

    def __str__(self):
        return f"Raw Statistics {self.uuid}"
