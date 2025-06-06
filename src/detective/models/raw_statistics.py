from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from detective.models import Company, Staging
import uuid
import os
from openai import OpenAI
from django.conf import settings
from pgvector.django import VectorField
import logging

logger = logging.getLogger(__name__)


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

    # Add category choices
    CATEGORY_ENVIRONMENTAL = "environmental"
    CATEGORY_SOCIAL = "social"
    CATEGORY_GOVERNANCE = "governance"
    CATEGORY_PRODUCT = "product"
    CATEGORY_GENERAL = "general"

    CATEGORY_CHOICES = [
        (CATEGORY_ENVIRONMENTAL, "Environmental"),
        (CATEGORY_SOCIAL, "Social"),
        (CATEGORY_GOVERNANCE, "Governance"),
        (CATEGORY_PRODUCT, "Product"),
        (CATEGORY_GENERAL, "General"),
    ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, default=None)
    staging = models.ManyToManyField(Staging)
    claim = models.TextField(default=None)
    evaluation = models.TextField()
    score = models.FloatField()
    score_breakdown = models.JSONField(null=True, blank=True)
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_GENERAL,  # Set default to GENERAL
        null=True,
        blank=True,
    )
    justification = models.JSONField(null=True, blank=True)
    recommendations = models.TextField(null=True, blank=True)
    processed = models.CharField(max_length=255, choices=PROCESSED_STATUSES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    defunct = models.BooleanField(default=False)
    comparison_analysis = models.JSONField(
        null=True, blank=True, help_text="Raw JSON response from claim comparison analysis"
    )
    # vector field for storing embeddings
    embedding = VectorField(
        dimensions=512,
        help_text="Vector embeddings for evaluation text",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"Raw Statistics {self.uuid}"

    def generate_embedding(self):
        """Generate embedding for claim text using OpenAI"""
        if not self.evaluation:
            return None

        open_ai_api_key = os.getenv("OPEN_AI_API_KEY", None)
        client = OpenAI(api_key=open_ai_api_key)

        response = client.embeddings.create(
            input=self.claim, model="text-embedding-3-large", dimensions=512
        )
        return response.data[0].embedding

    def find_similar_claims(self, limit=10):
        """Find similar claim based on current claim's embedding"""
        if not self.claim or self.embedding is None:
            return [], []

        from django.db import connection

        # Convert numpy array to list
        embedding_list = (
            self.embedding.tolist() if hasattr(self.embedding, "tolist") else self.embedding
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT uuid, evaluation, claim,
                    1 - (embedding <=> %s::vector) as similarity
                FROM detective_rawstatistics
                WHERE claim IS NOT NULL
                    AND defunct = FALSE
                    AND uuid != %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """,
                [embedding_list, self.uuid, embedding_list, limit],
            )

            # Get list of claims and evaluations
            results = cursor.fetchall()
            claims = [row[2] for row in results]
            evaluations = [row[1] for row in results]

            return claims, evaluations


@receiver(pre_save, sender=RawStatistics)
def create_embedding(sender, instance, **kwargs):
    """Create embedding before evaluation is saved, but only if evaluation is new or has changed"""
    try:
        if not instance.pk:  # New instance
            if instance.claim:
                instance.embedding = instance.generate_embedding()
        else:
            try:
                old_instance = RawStatistics.objects.get(pk=instance.pk)
                if instance.claim != old_instance.claim:
                    instance.embedding = instance.generate_embedding()
            except RawStatistics.DoesNotExist:
                # If old instance doesn't exist, treat it as a new instance
                if instance.claim:
                    instance.embedding = instance.generate_embedding()
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
