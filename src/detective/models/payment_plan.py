from django.db import models
import uuid


class PaymentPlan(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"

    BETA = "BETA"
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    PLAN_CHOICES = [
        (BETA, "Beta Plan"),
        (BASIC, "Basic Plan"),
        (PRO, "Pro Plan"),
        (ENTERPRISE, "Enterprise Plan"),
    ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=20, choices=PLAN_CHOICES, default="BETA", unique=True)
    max_reports = models.PositiveIntegerField(default=3)
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_name_display()
