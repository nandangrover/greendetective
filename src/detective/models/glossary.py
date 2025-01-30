from django.db import models
import uuid


class SustainabilityGlossary(models.Model):
    """
    Model to store sustainability-related terms and their definitions
    """

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the glossary term",
    )
    term = models.CharField(
        max_length=255, unique=True, help_text="The sustainability term or phrase"
    )
    definition = models.TextField(help_text="Detailed definition of the term", default="")
    context = models.TextField(blank=True, null=True, help_text="Additional context for the term")
    defunct = models.BooleanField(
        default=False,
        help_text="Mark if this term is no longer relevant or should be excluded from analysis",
    )
    source = models.CharField(max_length=255, help_text="Source of the term definition")
    category = models.CharField(
        max_length=255, blank=True, null=True, help_text="Category or grouping for the term"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the term was added"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the term was last updated"
    )

    class Meta:
        verbose_name = "Sustainability Glossary"
        verbose_name_plural = "Sustainability Glossaries"
        ordering = ["term"]

    def __str__(self):
        return f"{self.term} ({'Defunct' if self.defunct else 'Active'})"
