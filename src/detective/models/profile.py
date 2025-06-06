from django.db import models
from django.contrib.auth.models import User
from detective.models.business import Business
from django.db.models.signals import post_save
from django.dispatch import receiver
from detective.models.payment_plan import PaymentPlan
import uuid


class UserProfile(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, null=True, blank=True, related_name="profiles"
    )
    job_title = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    @property
    def business_user(self):
        """Returns the user associated with this business profile"""
        return self.user


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
